from backend.validator import ValidatedAction

def update_cooling_setpoint(value: float) -> dict:
    return {"cooling_setpoint": value}

def update_heating_setpoint(value: float) -> dict:
    return {"heating_setpoint": value}

def update_lighting(value: int) -> dict:
    return {"lighting_level": value}

def read_logs() -> dict:
    return {"status": "logs_available"}

TOOLS = {
    "update_cooling_setpoint": update_cooling_setpoint,
    "update_heating_setpoint": update_heating_setpoint,
    "update_lighting": update_lighting,
    "read_logs": read_logs,
}
