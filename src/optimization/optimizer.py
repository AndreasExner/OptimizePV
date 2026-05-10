"""Optimierungslogik für PV-Eigenverbrauch.

Regelbasierte Optimierung: Auf Basis der PV-Prognose und
Verbrauchsvorhersage werden Batterie- und Ladestrategie bestimmt.
"""

import pandas as pd
import numpy as np

from src.data.evcc_connector import (
    set_battery_mode,
    set_buffer_soc,
    set_priority_soc,
    set_smart_cost_limit,
    set_loadpoint_mode,
)


def create_schedule(
    pv_forecast: pd.DataFrame,
    consumption_forecast: pd.DataFrame | None = None,
    battery_capacity_kwh: float = 10.0,
    battery_soc: float = 50.0,
    feedin_price: float = 0.079,
    grid_price: float = 0.2586,
) -> pd.DataFrame:
    """Erstellt einen 24h-Optimierungsplan.

    Entscheidungslogik:
    1. Eigenverbrauch maximieren: Batterie laden wenn PV > Verbrauch
    2. Überschüssige PV in Batterie statt Einspeisung (7,9 ct < 25,9 ct)
    3. EV-Laden in PV-Überschuss-Zeiten verschieben

    Args:
        pv_forecast: DataFrame mit ['timestamp', 'pv_kwh'] (stündlich, 24h).
        consumption_forecast: Optional. DataFrame mit ['timestamp', 'consumption_kwh'].
        battery_capacity_kwh: Batteriekapazität in kWh.
        battery_soc: Aktueller Batterie-SoC in %.
        feedin_price: Einspeisevergütung EUR/kWh.
        grid_price: Netzbezugspreis EUR/kWh.

    Returns:
        DataFrame mit Optimierungsplan pro Stunde.
    """
    schedule = pv_forecast[["timestamp", "pv_kwh"]].copy()

    # Verbrauch ergänzen (Fallback: Durchschnitt)
    if consumption_forecast is not None and "consumption_kwh" in consumption_forecast.columns:
        schedule = pd.merge(schedule, consumption_forecast[["timestamp", "consumption_kwh"]],
                          on="timestamp", how="left")
    if "consumption_kwh" not in schedule.columns:
        schedule["consumption_kwh"] = 0.5  # Fallback: 0.5 kWh/h

    # Überschuss berechnen
    schedule["surplus_kwh"] = (schedule["pv_kwh"] - schedule["consumption_kwh"]).clip(lower=0)
    schedule["deficit_kwh"] = (schedule["consumption_kwh"] - schedule["pv_kwh"]).clip(lower=0)

    # Batterie-Status simulieren
    battery_kwh = battery_capacity_kwh * battery_soc / 100
    battery_actions = []

    for _, row in schedule.iterrows():
        surplus = row["surplus_kwh"]
        deficit = row["deficit_kwh"]

        if surplus > 0 and battery_kwh < battery_capacity_kwh:
            # PV-Überschuss → Batterie laden (statt einspeisen)
            charge = min(surplus, battery_capacity_kwh - battery_kwh)
            battery_kwh += charge
            battery_actions.append({
                "action": "charge",
                "battery_mode": "normal",
                "priority_soc": min(100, int(battery_kwh / battery_capacity_kwh * 100) + 10),
                "ev_mode": "pv",  # EV solar laden
                "reason": "PV-Überschuss → Batterie laden",
            })
        elif deficit > 0 and battery_kwh > battery_capacity_kwh * 0.1:
            # Verbrauch > PV → Batterie entladen (statt Netzbezug)
            discharge = min(deficit, battery_kwh - battery_capacity_kwh * 0.1)
            battery_kwh -= discharge
            battery_actions.append({
                "action": "discharge",
                "battery_mode": "normal",
                "priority_soc": 10,
                "ev_mode": "minpv",
                "reason": "PV < Verbrauch → Batterie entladen",
            })
        else:
            battery_actions.append({
                "action": "hold",
                "battery_mode": "normal",
                "priority_soc": 10,
                "ev_mode": "pv",
                "reason": "Ausgeglichen",
            })

    actions_df = pd.DataFrame(battery_actions)
    schedule = pd.concat([schedule.reset_index(drop=True), actions_df], axis=1)
    schedule["battery_soc_projected"] = 0.0

    # SoC-Projektion rückwärts berechnen
    soc = battery_soc
    soc_values = [soc]
    for i in range(1, len(schedule)):
        row = schedule.iloc[i]
        if row["action"] == "charge":
            soc = min(100, soc + row["surplus_kwh"] / battery_capacity_kwh * 100)
        elif row["action"] == "discharge":
            soc = max(10, soc - row["deficit_kwh"] / battery_capacity_kwh * 100)
        soc_values.append(soc)
    schedule["battery_soc_projected"] = soc_values

    return schedule


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
