from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, csv
from backend.config import ConfigManager, get_logger

logger = get_logger("collector")

@dataclass
class RawBuildingState:
    timestamp: str
    zone_temperature: float
    humidity: float
    occupancy: int
    hvac_energy: float
    lighting_energy: float
    pmv: float

    def to_dict(self):
        return asdict(self)

class BuildingStateCollector:
    def __init__(self, config: ConfigManager):
        self.cfg = config
        self.snap_dir = self.cfg.simulation.demo_snapshot_directory
        self._idx = 0

    def collect(self) -> RawBuildingState:
        if self.cfg.simulation.demo_mode:
            files = sorted(Path(self.snap_dir).glob("*.json"))
            if not files:
                raise FileNotFoundError("No demo snapshots found.")
            f = files[min(self._idx, len(files)-1)]
            self._idx += 1
            data = json.loads(f.read_text())
            return RawBuildingState(**data)

        csv_path = Path(self.cfg.simulation.output_directory) / "eplusout.csv"
        if not csv_path.exists():
            raise FileNotFoundError(csv_path)

        with csv_path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        if not rows:
            raise RuntimeError("EnergyPlus output CSV empty.")
        r = rows[-1]

        def g(*names, default=0.0):
            for n in names:
                if n in r:
                    try:
                        return float(r[n])
                    except:
                        return default
            return default

        return RawBuildingState(
            timestamp=r.get("Date/Time",""),
            zone_temperature=g("Zone Mean Air Temperature"),
            humidity=g("Zone Air Relative Humidity"),
            occupancy=int(g("People Occupant Count")),
            hvac_energy=g("Cooling:Electricity","Heating:Electricity"),
            lighting_energy=g("InteriorLights:Electricity"),
            pmv=g("Zone Thermal Comfort Fanger Model PMV", default=0.0)
        )
