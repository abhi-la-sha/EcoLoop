from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR: Path = PROJECT_ROOT / "config"
DEFAULT_LOG_DIR: Path = PROJECT_ROOT / "logs"
DEFAULT_LOG_FILE: Path = DEFAULT_LOG_DIR / "project.log"

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_LOGGING_CONFIGURED = False
_LOGGER_NAMESPACE = "ecoloop"


class ConfigError(Exception):
    pass
@dataclass(frozen=True)
class SimulationConfig:

    energyplus_path: Path
    idf_path: Path
    weather_path: Path
    output_directory: Path
    demo_mode: bool
    demo_snapshot_directory: Path
    max_retry: int
    timestep_interval: int


@dataclass(frozen=True)
class OccupancyThreshold:

    low_max: int
    medium_max: int


@dataclass(frozen=True)
class HVACLimits:
    
    cooling_min: float
    cooling_max: float
    heating_min: float
    heating_max: float


@dataclass(frozen=True)
class BuildingConfig:
    
    min_temperature: float
    max_temperature: float
    min_pmv: float
    max_pmv: float
    occupancy_threshold: OccupancyThreshold
    hvac_limits: HVACLimits


@dataclass(frozen=True)
class LLMConfig:
    
    provider: str
    model: str
    temperature: float
    max_tokens: int
    timeout: int


@dataclass(frozen=True)
class AppConfig:

    simulation: SimulationConfig
    building: BuildingConfig
    llm: LLMConfig
    project_root: Path
    config_dir: Path


def get_logger(name: str) -> logging.Logger:
    
    return logging.getLogger(f"{_LOGGER_NAMESPACE}.{name}")


def setup_logging(
    log_dir: Path | None = None,
    log_level: int = logging.INFO,
) -> None:
    
    global _LOGGING_CONFIGURED

    if _LOGGING_CONFIGURED:
        return

    resolved_log_dir = log_dir or DEFAULT_LOG_DIR
    resolved_log_dir.mkdir(parents=True, exist_ok=True)
    log_file = resolved_log_dir / "project.log"

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    root_logger = logging.getLogger(_LOGGER_NAMESPACE)
    root_logger.setLevel(log_level)
    root_logger.propagate = False

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    _LOGGING_CONFIGURED = True


def ensure_project_directories(project_root: Path | None = None) -> None:
    
    root = project_root or PROJECT_ROOT
    directories = (
        root / "logs",
        root / "results",
        root / "results" / "baseline",
        root / "results" / "optimized",
        root / "energyplus",
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


class ConfigManager:
    

    _SIMULATION_REQUIRED_KEYS = frozenset(
        {
            "energyplus_path",
            "idf_path",
            "weather_path",
            "output_directory",
            "demo_mode",
            "demo_snapshot_directory",
            "max_retry",
            "timestep_interval",
        }
    )
    _BUILDING_REQUIRED_KEYS = frozenset(
        {
            "min_temperature",
            "max_temperature",
            "min_pmv",
            "max_pmv",
            "occupancy_threshold",
            "hvac_limits",
        }
    )
    _LLM_REQUIRED_KEYS = frozenset(
        {"provider", "model", "temperature", "max_tokens", "timeout"}
    )

    def __init__(
        self,
        config_dir: Path | str | None = None,
        project_root: Path | str | None = None,
    ) -> None:

        self._project_root = Path(project_root).resolve() if project_root else PROJECT_ROOT
        self._config_dir = (
            Path(config_dir).resolve()
            if config_dir
            else self._project_root / "config"
        )
        self._app_config: AppConfig | None = None
        self._logger = get_logger("config")

    @property
    def is_loaded(self) -> bool:

        return self._app_config is not None

    @property
    def config(self) -> AppConfig:

        if self._app_config is None:
            raise ConfigError(
                "Configuration has not been loaded. Call load() first."
            )
        return self._app_config

    @property
    def simulation(self) -> SimulationConfig:

        return self.config.simulation

    @property
    def building(self) -> BuildingConfig:

        return self.config.building

    @property
    def llm(self) -> LLMConfig:

        return self.config.llm

    def load(self, setup_logs: bool = True) -> AppConfig:
        
        ensure_project_directories(self._project_root)

        if setup_logs:
            setup_logging(log_dir=self._project_root / "logs")

        self._logger.info("Loading configuration from %s", self._config_dir)

        simulation_data = self._load_yaml_file("simulation.yaml")
        building_data = self._load_yaml_file("building.yaml")
        llm_data = self._load_yaml_file("llm.yaml")

        simulation = self._parse_simulation_config(simulation_data)
        building = self._parse_building_config(building_data)
        llm = self._parse_llm_config(llm_data)

        
        simulation.demo_snapshot_directory.mkdir(parents=True, exist_ok=True)

        self._app_config = AppConfig(
            simulation=simulation,
            building=building,
            llm=llm,
            project_root=self._project_root,
            config_dir=self._config_dir,
        )

        self._logger.info("Configuration loaded successfully")
        return self._app_config

    def _load_yaml_file(self, filename: str) -> dict[str, Any]:
        
        file_path = self._config_dir / filename

        if not file_path.exists():
            raise ConfigError(f"Missing configuration file: {file_path}")

        try:
            with file_path.open(encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML in {file_path}: {exc}") from exc
        except OSError as exc:
            raise ConfigError(f"Unable to read {file_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ConfigError(
                f"Configuration file must contain a YAML mapping: {file_path}"
            )

        return data

    def _parse_simulation_config(self, data: dict[str, Any]) -> SimulationConfig:
        
        self._ensure_required_keys(data, self._SIMULATION_REQUIRED_KEYS, "simulation.yaml")

        demo_mode = self._require_bool(data, "demo_mode", "simulation.yaml")
        max_retry = self._require_int(data, "max_retry", "simulation.yaml", min_value=0)
        timestep_interval = self._require_int(
            data, "timestep_interval", "simulation.yaml", min_value=1
        )

        return SimulationConfig(
            energyplus_path=self._resolve_path(
                self._require_str(data, "energyplus_path", "simulation.yaml"),
                "simulation.yaml",
                "energyplus_path",
            ),
            idf_path=self._resolve_path(
                self._require_str(data, "idf_path", "simulation.yaml"),
                "simulation.yaml",
                "idf_path",
            ),
            weather_path=self._resolve_path(
                self._require_str(data, "weather_path", "simulation.yaml"),
                "simulation.yaml",
                "weather_path",
            ),
            output_directory=self._resolve_path(
                self._require_str(data, "output_directory", "simulation.yaml"),
                "simulation.yaml",
                "output_directory",
            ),
            demo_mode=demo_mode,
            demo_snapshot_directory=self._resolve_path(
                self._require_str(data, "demo_snapshot_directory", "simulation.yaml"),
                "simulation.yaml",
                "demo_snapshot_directory",
            ),
            max_retry=max_retry,
            timestep_interval=timestep_interval,
        )

    def _parse_building_config(self, data: dict[str, Any]) -> BuildingConfig:

        self._ensure_required_keys(data, self._BUILDING_REQUIRED_KEYS, "building.yaml")

        min_temperature = self._require_float(
            data, "min_temperature", "building.yaml"
        )
        max_temperature = self._require_float(
            data, "max_temperature", "building.yaml"
        )
        min_pmv = self._require_float(data, "min_pmv", "building.yaml", min_value=-3.0, max_value=3.0)
        max_pmv = self._require_float(data, "max_pmv", "building.yaml", min_value=-3.0, max_value=3.0)

        if min_temperature >= max_temperature:
            raise ConfigError(
                "building.yaml: min_temperature must be less than max_temperature"
            )

        if min_pmv >= max_pmv:
            raise ConfigError("building.yaml: min_pmv must be less than max_pmv")

        occupancy_raw = data["occupancy_threshold"]
        if not isinstance(occupancy_raw, dict):
            raise ConfigError(
                "building.yaml: 'occupancy_threshold' must be a mapping with "
                "'low_max' and 'medium_max'"
            )

        low_max = self._require_nested_int(
            occupancy_raw, "low_max", "building.yaml", "occupancy_threshold", min_value=0
        )
        medium_max = self._require_nested_int(
            occupancy_raw, "medium_max", "building.yaml", "occupancy_threshold", min_value=0
        )

        if low_max >= medium_max:
            raise ConfigError(
                "building.yaml: occupancy_threshold.low_max must be less than "
                "occupancy_threshold.medium_max"
            )

        hvac_raw = data["hvac_limits"]
        if not isinstance(hvac_raw, dict):
            raise ConfigError(
                "building.yaml: 'hvac_limits' must be a mapping with cooling/heating bounds"
            )

        cooling_min = self._require_nested_float(
            hvac_raw, "cooling_min", "building.yaml", "hvac_limits"
        )
        cooling_max = self._require_nested_float(
            hvac_raw, "cooling_max", "building.yaml", "hvac_limits"
        )
        heating_min = self._require_nested_float(
            hvac_raw, "heating_min", "building.yaml", "hvac_limits"
        )
        heating_max = self._require_nested_float(
            hvac_raw, "heating_max", "building.yaml", "hvac_limits"
        )

        if cooling_min >= cooling_max:
            raise ConfigError(
                "building.yaml: hvac_limits.cooling_min must be less than cooling_max"
            )

        if heating_min >= heating_max:
            raise ConfigError(
                "building.yaml: hvac_limits.heating_min must be less than heating_max"
            )

        return BuildingConfig(
            min_temperature=min_temperature,
            max_temperature=max_temperature,
            min_pmv=min_pmv,
            max_pmv=max_pmv,
            occupancy_threshold=OccupancyThreshold(
                low_max=low_max,
                medium_max=medium_max,
            ),
            hvac_limits=HVACLimits(
                cooling_min=cooling_min,
                cooling_max=cooling_max,
                heating_min=heating_min,
                heating_max=heating_max,
            ),
        )

    def _parse_llm_config(self, data: dict[str, Any]) -> LLMConfig:
        
        self._ensure_required_keys(data, self._LLM_REQUIRED_KEYS, "llm.yaml")

        provider = self._require_str(data, "provider", "llm.yaml")
        model = self._require_str(data, "model", "llm.yaml")
        temperature = self._require_float(
            data, "temperature", "llm.yaml", min_value=0.0, max_value=2.0
        )
        max_tokens = self._require_int(data, "max_tokens", "llm.yaml", min_value=1)
        timeout = self._require_int(data, "timeout", "llm.yaml", min_value=1)

        return LLMConfig(
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def _resolve_path(self, value: str, file_name: str, key_name: str) -> Path:
        
        if not value.strip():
            raise ConfigError(f"{file_name}: '{key_name}' must be a non-empty path string")

        path = Path(value)
        if path.is_absolute():
            return path
        return (self._project_root / path).resolve()

    @staticmethod
    def _ensure_required_keys(
        data: dict[str, Any],
        required_keys: frozenset[str],
        file_name: str,
    ) -> None:
        
        missing = sorted(required_keys - data.keys())
        if missing:
            joined = ", ".join(missing)
            raise ConfigError(f"{file_name}: missing required key(s): {joined}")

    @staticmethod
    def _require_str(data: dict[str, Any], key: str, file_name: str) -> str:
        
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{file_name}: '{key}' must be a non-empty string")
        return value.strip()

    @staticmethod
    def _require_bool(data: dict[str, Any], key: str, file_name: str) -> bool:
        
        value = data.get(key)
        if not isinstance(value, bool):
            raise ConfigError(f"{file_name}: '{key}' must be a boolean (true/false)")
        return value

    @staticmethod
    def _require_int(
        data: dict[str, Any],
        key: str,
        file_name: str,
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> int:
        
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{file_name}: '{key}' must be an integer")
        ConfigManager._validate_numeric_range(value, key, file_name, min_value, max_value)
        return value

    @staticmethod
    def _require_float(
        data: dict[str, Any],
        key: str,
        file_name: str,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> float:
        
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{file_name}: '{key}' must be a number")
        float_value = float(value)
        ConfigManager._validate_numeric_range(float_value, key, file_name, min_value, max_value)
        return float_value

    @staticmethod
    def _require_nested_int(
        data: dict[str, Any],
        key: str,
        file_name: str,
        parent_key: str,
        min_value: int | None = None,
        max_value: int | None = None,
    ) -> int:
        
        value = data.get(key)
        label = f"{file_name}: '{parent_key}.{key}'"
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{label} must be an integer")
        ConfigManager._validate_numeric_range(value, f"{parent_key}.{key}", file_name, min_value, max_value)
        return value

    @staticmethod
    def _require_nested_float(
        data: dict[str, Any],
        key: str,
        file_name: str,
        parent_key: str,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> float:
        
        value = data.get(key)
        label = f"{file_name}: '{parent_key}.{key}'"
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"{label} must be a number")
        float_value = float(value)
        ConfigManager._validate_numeric_range(
            float_value, f"{parent_key}.{key}", file_name, min_value, max_value
        )
        return float_value

    @staticmethod
    def _validate_numeric_range(
        value: float | int,
        key: str,
        file_name: str,
        min_value: float | int | None,
        max_value: float | int | None,
    ) -> None:
        
        if min_value is not None and value < min_value:
            raise ConfigError(
                f"{file_name}: '{key}' must be greater than or equal to {min_value}"
            )
        if max_value is not None and value > max_value:
            raise ConfigError(
                f"{file_name}: '{key}' must be less than or equal to {max_value}"
            )


def load_config(
    config_dir: Path | str | None = None,
    project_root: Path | str | None = None,
    setup_logs: bool = True,
) -> AppConfig:
    
    manager = ConfigManager(config_dir=config_dir, project_root=project_root)
    return manager.load(setup_logs=setup_logs)


if __name__ == "__main__":
    app_config = load_config()
    logger = get_logger("config")
    logger.info("Project root: %s", app_config.project_root)
    logger.info("Demo mode: %s", app_config.simulation.demo_mode)
    logger.info("IDF path (placeholder): %s", app_config.simulation.idf_path)
    logger.info("Weather path (placeholder): %s", app_config.simulation.weather_path)
    logger.info("Temperature range: %s-%s C", app_config.building.min_temperature, app_config.building.max_temperature)
    logger.info("LLM model: %s", app_config.llm.model)
