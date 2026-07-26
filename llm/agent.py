from __future__ import annotations
import requests
from backend.rule_engine import ProcessedFeatures
from backend.config import ConfigManager, get_logger

logger = get_logger("agent")

class LLMAgent:
    def __init__(self, config: ConfigManager):
        self.cfg = config
        self.url = getattr(self.cfg.llm, "base_url", "http://localhost:11434/api/generate")
        self.model = self.cfg.llm.model

    def decide(self, features: ProcessedFeatures) -> dict:
        prompt = f"""
You are an energy optimization assistant.

Occupancy: {features.occupancy_level}
Comfort OK: {features.comfort_ok}
High Load: {features.high_energy_load}
High Carbon: {features.high_carbon_period}

Return ONLY JSON:
{{
 "cooling_setpoint": number,
 "heating_setpoint": number,
 "lighting_level": number
}}
"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            response = requests.post(self.url, json=payload, timeout=20)
            response.raise_for_status()
            text = response.json().get("response", "").strip()

            import json
            start = text.find("{")
            end = text.rfind("}") + 1
            return json.loads(text[start:end])

        except Exception as ex:
            logger.warning("LLM unavailable. Using fallback. %s", ex)

            return {
                "cooling_setpoint": features.recommended_cooling,
                "heating_setpoint": features.recommended_heating,
                "lighting_level": features.recommended_lighting,
            }
