from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from backend.config import ConfigManager, get_logger
SUMMARY_FILENAME = "simulation_summary.json"


@dataclass
class RunMetrics:
    
    total_energy_kwh: float
    hvac_energy_kwh: float
    average_temperature: float
    average_pmv: float
    runtime_seconds: float
    comfort_maintained: bool


@dataclass
class SavingsMetrics:

    energy_saved_percent: float
    hvac_saved_percent: float
    comfort_change: float


@dataclass
class ComparisonMetrics:

    baseline: RunMetrics
    optimized: RunMetrics
    savings: SavingsMetrics
    applied_actions: list[dict] = field(default_factory=list)
    ai_recommendations: list[str] = field(default_factory=list)
    timestamp: str = ""


class MetricsGenerator:

    def __init__(self, config: ConfigManager):
        self.cfg = config
        self.logger = get_logger("metrics")
        root = self.cfg.config.project_root
        self.baseline_dir = root / "results" / "baseline"
        self.optimized_dir = root / "results" / "optimized"
        self.output_file = root / "results" / "comparison.json"

    def _read_summary(self, folder: Path) -> dict:
        summary_path = folder / SUMMARY_FILENAME
        if not summary_path.exists():
            raise FileNotFoundError(f"No simulation summary found: {summary_path}")

        with summary_path.open(encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def _to_run_metrics(data: dict, summary_path: Path) -> RunMetrics:
        try:
            return RunMetrics(
                total_energy_kwh=float(data["total_energy_kwh"]),
                hvac_energy_kwh=float(data["hvac_energy_kwh"]),
                average_temperature=float(data["average_temperature"]),
                average_pmv=float(data["average_pmv"]),
                runtime_seconds=float(data.get("runtime_seconds", 0.0)),
                comfort_maintained=bool(data.get("comfort_maintained", False)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Malformed simulation summary: {summary_path}") from exc

    @staticmethod
    def _percent_saved(baseline_value: float, optimized_value: float) -> float:
        if not baseline_value:
            return 0.0
        return (baseline_value - optimized_value) / baseline_value * 100

    def generate(self) -> ComparisonMetrics:
        baseline_raw = self._read_summary(self.baseline_dir)
        optimized_raw = self._read_summary(self.optimized_dir)

        baseline = self._to_run_metrics(baseline_raw, self.baseline_dir / SUMMARY_FILENAME)
        optimized = self._to_run_metrics(optimized_raw, self.optimized_dir / SUMMARY_FILENAME)

        savings = SavingsMetrics(
            energy_saved_percent=round(
                self._percent_saved(baseline.total_energy_kwh, optimized.total_energy_kwh), 2
            ),
            hvac_saved_percent=round(
                self._percent_saved(baseline.hvac_energy_kwh, optimized.hvac_energy_kwh), 2
            ),
            comfort_change=round(optimized.average_pmv - baseline.average_pmv, 2),
        )

        metrics = ComparisonMetrics(
            baseline=RunMetrics(
                total_energy_kwh=round(baseline.total_energy_kwh, 2),
                hvac_energy_kwh=round(baseline.hvac_energy_kwh, 2),
                average_temperature=round(baseline.average_temperature, 2),
                average_pmv=round(baseline.average_pmv, 2),
                runtime_seconds=round(baseline.runtime_seconds, 3),
                comfort_maintained=baseline.comfort_maintained,
            ),
            optimized=RunMetrics(
                total_energy_kwh=round(optimized.total_energy_kwh, 2),
                hvac_energy_kwh=round(optimized.hvac_energy_kwh, 2),
                average_temperature=round(optimized.average_temperature, 2),
                average_pmv=round(optimized.average_pmv, 2),
                runtime_seconds=round(optimized.runtime_seconds, 3),
                comfort_maintained=optimized.comfort_maintained,
            ),
            savings=savings,
            applied_actions=optimized_raw.get("applied_actions", []),
            ai_recommendations=optimized_raw.get("ai_recommendations", []),
            timestamp=datetime.now().isoformat(timespec="seconds"),
        )

        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        with self.output_file.open("w", encoding="utf-8") as f:
            json.dump(asdict(metrics), f, indent=4)

        self.logger.info("Comparison metrics written to %s", self.output_file)
        return metrics


if __name__ == "__main__":
    cfg = ConfigManager()
    cfg.load()
    m = MetricsGenerator(cfg).generate()
    print(m)