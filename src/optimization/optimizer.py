"""Optimierungslogik für PV-Eigenverbrauch.

Regelbasierte Optimierung: Auf Basis der prognostizierten PV-Modulleistung
und Verbrauchsvorhersage werden Batterie- und Ladestrategie bestimmt.

Die Modulleistung (bis 13,4 kWp) wird auf die verfügbaren Pfade aufgeteilt:
- AC-Ausgang (max 10 kW) → Haus, Grid, EV, WP
- DC-Batterie (max 5 kW Laden / 5 kW Entladen)
"""

import pandas as pd

from src.config import PV_SPECS
from src.data.evcc_connector import (
    set_battery_mode,
    set_priority_soc,
    set_loadpoint_mode,
)


def create_schedule(
    pv_module_forecast: pd.DataFrame,
    consumption_forecast: pd.DataFrame | None = None,
    battery_soc: float = 50.0,
    feedin_price: float = 0.079,
    grid_price: float = 0.2586,
) -> pd.DataFrame:
    """Erstellt einen 24h-Optimierungsplan.

    Nimmt die prognostizierte PV-Modulleistung (kWh/h) und verteilt sie
    auf AC-Ausgang und Batterie unter Berücksichtigung der Hardware-Limits.

    Entscheidungslogik:
    1. Eigenverbrauch maximieren: Batterie laden wenn PV > AC-Verbrauch
    2. Überschüssige PV in Batterie statt Einspeisung (7,9 ct < 25,9 ct)
    3. EV/WP-Laden in PV-Überschuss-Zeiten verschieben

    Args:
        pv_module_forecast: DataFrame mit ['timestamp', 'pv_module_kwh'].
        consumption_forecast: Optional. DataFrame mit ['timestamp', 'home_kwh'].
        battery_soc: Aktueller Batterie-SoC in %.
        feedin_price: Einspeisevergütung EUR/kWh.
        grid_price: Netzbezugspreis EUR/kWh.

    Returns:
        DataFrame mit Optimierungsplan pro Stunde.
    """
    inverter_max = PV_SPECS["inverter_max_kw"]
    bat_capacity = PV_SPECS["battery_capacity_kwh"]
    bat_max_charge = PV_SPECS["battery_max_charge_kw"]
    bat_max_discharge = PV_SPECS["battery_max_discharge_kw"]
    bat_min_soc = PV_SPECS["battery_min_soc_pct"]

    schedule = pv_module_forecast[["timestamp", "pv_module_kwh"]].copy()

    # Verbrauch ergänzen (Fallback: Durchschnitt)
    if consumption_forecast is not None and "home_kwh" in consumption_forecast.columns:
        schedule = pd.merge(schedule, consumption_forecast[["timestamp", "home_kwh"]],
                          on="timestamp", how="left")
    if "home_kwh" not in schedule.columns:
        schedule["home_kwh"] = 0.5  # Fallback: 0.5 kWh/h

    # Batterie-Status simulieren
    bat_kwh = bat_capacity * battery_soc / 100
    bat_min_kwh = bat_capacity * bat_min_soc / 100
    results = []

    for _, row in schedule.iterrows():
        module_kwh = row["pv_module_kwh"]
        consumption = row["home_kwh"]

        # Schritt 1: AC-Verfügbarkeit (WR-Limit)
        pv_ac_kwh = min(module_kwh, inverter_max)

        # Schritt 2: Batterie-Ladung aus DC-Überschuss (Module > WR-Limit)
        dc_surplus = max(0, module_kwh - inverter_max)
        bat_charge_dc = min(dc_surplus, bat_max_charge, bat_capacity - bat_kwh)

        # Schritt 3: AC-Überschuss / -Defizit
        ac_surplus = max(0, pv_ac_kwh - consumption)
        ac_deficit = max(0, consumption - pv_ac_kwh)

        # Schritt 4: AC-Überschuss auch in Batterie (sofern noch Platz)
        bat_charge_ac = min(ac_surplus, bat_max_charge - bat_charge_dc,
                           bat_capacity - bat_kwh - bat_charge_dc)
        bat_charge_total = bat_charge_dc + bat_charge_ac

        # Schritt 5: Bei Defizit → Batterie entladen
        bat_discharge = 0
        if ac_deficit > 0:
            bat_discharge = min(ac_deficit, bat_max_discharge, bat_kwh - bat_min_kwh)

        # Schritt 6: Verbleibendes Defizit / Überschuss → Grid
        grid_import = max(0, ac_deficit - bat_discharge)
        grid_export = max(0, ac_surplus - bat_charge_ac)

        # Batterie-SoC aktualisieren
        bat_kwh += bat_charge_total - bat_discharge
        bat_kwh = max(bat_min_kwh, min(bat_capacity, bat_kwh))

        # Verfügbar für große Verbraucher (EV/WP)
        available_for_loads = max(0, pv_ac_kwh - consumption + bat_discharge)

        results.append({
            "timestamp": row["timestamp"],
            "pv_module_kwh": module_kwh,
            "pv_ac_kwh": pv_ac_kwh,
            "home_kwh": consumption,
            "battery_charge_kwh": bat_charge_total,
            "battery_discharge_kwh": bat_discharge,
            "battery_soc_projected": bat_kwh / bat_capacity * 100,
            "grid_import_kwh": grid_import,
            "grid_export_kwh": grid_export,
            "available_for_loads_kwh": available_for_loads,
            # Steuerungsbefehle
            "action": "charge" if bat_charge_total > 0.1 else ("discharge" if bat_discharge > 0.1 else "hold"),
            "battery_mode": "normal",
            "priority_soc": min(100, int(bat_kwh / bat_capacity * 100) + 10),
            "ev_mode": "pv" if available_for_loads > 1.0 else "minpv",
            "reason": (
                f"Module {module_kwh:.1f}kWh → AC {pv_ac_kwh:.1f} + Bat {bat_charge_total:.1f}, "
                f"verfügbar für EV/WP: {available_for_loads:.1f}kWh"
            ),
        })

    return pd.DataFrame(results)


def apply_schedule_step(schedule_row: pd.Series, loadpoint_id: int = 1) -> None:
    """Wendet eine einzelne Zeile des Optimierungsplans auf evcc an.

    ACHTUNG: Battery-Mode hat 60s-Watchdog – muss regelmäßig erneuert werden.

    Args:
        schedule_row: Eine Zeile aus dem Schedule-DataFrame.
        loadpoint_id: Loadpoint-ID für EV-Steuerung.
    """
    set_battery_mode(schedule_row["battery_mode"])
    set_priority_soc(schedule_row["priority_soc"])
    set_loadpoint_mode(loadpoint_id, schedule_row["ev_mode"])
