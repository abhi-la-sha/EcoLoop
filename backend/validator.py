from dataclasses import dataclass
from backend.config import ConfigManager

@dataclass
class ValidatedAction:
    cooling_setpoint: float
    heating_setpoint: float
    lighting_level: int
    corrections: list[str]

class ActionValidator:
    def __init__(self, config: ConfigManager):
        self.cfg = config

    def validate(self, action: dict) -> ValidatedAction:
        hvac = self.cfg.building.hvac_limits
        corrections = []

        cool = float(action.get("cooling_setpoint", 24))
        if cool < hvac.cooling_min:
            corrections.append(f"Cooling raised to {hvac.cooling_min}")
            cool = hvac.cooling_min
        if cool > hvac.cooling_max:
            corrections.append(f"Cooling lowered to {hvac.cooling_max}")
            cool = hvac.cooling_max

        heat = float(action.get("heating_setpoint", 20))
        if heat < hvac.heating_min:
            corrections.append(f"Heating raised to {hvac.heating_min}")
            heat = hvac.heating_min
        if heat > hvac.heating_max:
            corrections.append(f"Heating lowered to {hvac.heating_max}")
            heat = hvac.heating_max

        light = int(action.get("lighting_level", 100))
        light = max(0, min(100, light))

        return ValidatedAction(cool, heat, light, corrections)
