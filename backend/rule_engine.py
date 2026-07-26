from __future__ import annotations
from dataclasses import dataclass, asdict
from backend.collector import RawBuildingState
from backend.config import ConfigManager

@dataclass
class ProcessedFeatures:
    occupancy_level:str
    comfort_ok:bool
    high_energy_load:bool
    high_carbon_period:bool
    recommended_cooling:float
    recommended_heating:float
    recommended_lighting:int
    raw:RawBuildingState

    def to_dict(self):
        d=asdict(self)
        d["raw"]=self.raw.to_dict()
        return d

class RuleEngine:
    def __init__(self,config:ConfigManager):
        self.cfg=config

    def process(self,state:RawBuildingState)->ProcessedFeatures:
        b=self.cfg.building
        occ=state.occupancy
        if occ<=b.occupancy_threshold.low_max:
            level="LOW"
        elif occ<=b.occupancy_threshold.medium_max:
            level="MEDIUM"
        else:
            level="HIGH"
        comfort=b.min_temperature<=state.zone_temperature<=b.max_temperature
        high_load=state.hvac_energy>20
        hour=0
        try:
            hour=int(state.timestamp.split()[1].split(":")[0])
        except Exception:
            pass
        high_carbon=17<=hour<=21
        cool=24.0 if level=="LOW" else 23.0 if level=="MEDIUM" else 22.0
        heat=20.0
        light=30 if level=="LOW" else 70 if level=="MEDIUM" else 100
        return ProcessedFeatures(level,comfort,high_load,high_carbon,cool,heat,light,state)
