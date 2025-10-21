
# app/schemas/standards.py
from pydantic import BaseModel
from typing import Dict, Optional

class StandardsConfig(BaseModel):
    # Optional symbol library mapping (tag type -> DXF file path)
    # Example in standards/active.json:
    # "symbols": {
    #   "receptacle": "symbols/rec.dxf",
    #   "luminaire": "symbols/2x2.dxf",
    #   "panel": "symbols/panel.dxf",
    #   "switch": "symbols/switch.dxf"
    # }
    symbols: Optional[Dict[str, str]] = None

    # Layer mappings
    layers: Dict[str, str] = {
        "power_devices": "E-POWR-DEV",
        "lighting": "E-LITE-FIXT",
        "panels": "E-POWR-PNLS",
        "annotations": "E-ANNO-TEXT",
        "rooms": "E-ANNO-ROOM",
    }

    # Styles
    text_style: Optional[str] = "Standard"
    dim_style: Optional[str] = "Standard"

    # Optional: Titleblock DXF file (relative path under /standards or absolute)
    titleblock: Optional[str] = None