"""Home Assistant Daten-Connector (DEPRECATED).

Dieses Modul wird nicht mehr verwendet. Das Projekt nutzt ausschließlich evcc
als Schnittstelle zur PV-Hardware (siehe evcc_connector.py).

Dieses Modul bleibt als Referenz erhalten, wird aber nicht mehr weiterentwickelt.
"""

import warnings

warnings.warn(
    "ha_connector ist deprecated – bitte evcc_connector verwenden.",
    DeprecationWarning,
    stacklevel=2,
)
