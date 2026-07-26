
from pathlib import Path
import json
from backend.validator import ValidatedAction
from backend.config import ConfigManager, get_logger

logger = get_logger("controller")

class ActuatorController:

    def __init__(self, config: ConfigManager):
        self.cfg = config
        self.audit_file = Path(self.cfg.simulation.output_directory) / "controller_actions.json"

    def apply(self, action: ValidatedAction) -> None:
        record = {
            "cooling_setpoint": action.cooling_setpoint,
            "heating_setpoint": action.heating_setpoint,
            "lighting_level": action.lighting_level,
            "corrections": action.corrections,
        }

        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        self.audit_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
        logger.info("Applied validated control action.")
