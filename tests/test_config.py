from __future__ import annotations
from pathlib import Path
import pytest
import yaml
from backend.config import ConfigError, ConfigManager

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"

class TestConfigManagerSuccess:
   
    def test_load_default_configuration(self) -> None:
        
        manager = ConfigManager(project_root=PROJECT_ROOT, config_dir=DEFAULT_CONFIG_DIR)
        app_config = manager.load(setup_logs=False)

        assert manager.is_loaded
        assert app_config.simulation.demo_mode is False
        assert app_config.simulation.max_retry == 1
        assert app_config.simulation.timestep_interval == 15
        assert app_config.building.min_temperature == 22.0
        assert app_config.building.max_temperature == 25.0
        assert app_config.building.occupancy_threshold.low_max == 5
        assert app_config.building.hvac_limits.cooling_max == 28.0
        assert app_config.llm.provider == "ollama"
        assert app_config.llm.model == "qwen2.5"

    def test_relative_paths_resolve_from_project_root(self) -> None:
        
        manager = ConfigManager(project_root=PROJECT_ROOT, config_dir=DEFAULT_CONFIG_DIR)
        app_config = manager.load(setup_logs=False)

        assert app_config.simulation.idf_path == (PROJECT_ROOT / "energyplus/building.idf").resolve()
        assert app_config.simulation.weather_path == (PROJECT_ROOT / "energyplus/weather.epw").resolve()


class TestConfigManagerMissingFiles:

    def test_missing_yaml_file_raises_config_error(self, tmp_path: Path) -> None:
        
        empty_config_dir = tmp_path / "config"
        empty_config_dir.mkdir()

        manager = ConfigManager(project_root=tmp_path, config_dir=empty_config_dir)

        with pytest.raises(ConfigError, match="Missing configuration file"):
            manager.load(setup_logs=False)


class TestConfigManagerInvalidValues:

    def test_invalid_temperature_range_raises_config_error(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        self._write_minimal_valid_configs(config_dir)

        building_path = config_dir / "building.yaml"
        building_data = yaml.safe_load(building_path.read_text(encoding="utf-8"))
        building_data["min_temperature"] = 30.0
        building_data["max_temperature"] = 20.0
        building_path.write_text(yaml.safe_dump(building_data), encoding="utf-8")

        manager = ConfigManager(project_root=tmp_path, config_dir=config_dir)

        with pytest.raises(ConfigError, match="min_temperature must be less than max_temperature"):
            manager.load(setup_logs=False)

    def test_invalid_llm_temperature_raises_config_error(self, tmp_path: Path) -> None:
        
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        self._write_minimal_valid_configs(config_dir)

        llm_path = config_dir / "llm.yaml"
        llm_data = yaml.safe_load(llm_path.read_text(encoding="utf-8"))
        llm_data["temperature"] = 5.0
        llm_path.write_text(yaml.safe_dump(llm_data), encoding="utf-8")

        manager = ConfigManager(project_root=tmp_path, config_dir=config_dir)

        with pytest.raises(ConfigError, match="temperature"):
            manager.load(setup_logs=False)

    def test_missing_required_key_raises_config_error(self, tmp_path: Path) -> None:
        
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        self._write_minimal_valid_configs(config_dir)

        simulation_path = config_dir / "simulation.yaml"
        simulation_data = yaml.safe_load(simulation_path.read_text(encoding="utf-8"))
        del simulation_data["demo_mode"]
        simulation_path.write_text(yaml.safe_dump(simulation_data), encoding="utf-8")

        manager = ConfigManager(project_root=tmp_path, config_dir=config_dir)

        with pytest.raises(ConfigError, match="missing required key"):
            manager.load(setup_logs=False)

    @staticmethod
    def _write_minimal_valid_configs(config_dir: Path) -> None:
        
        (config_dir / "simulation.yaml").write_text(
            yaml.safe_dump(
                {
                    "energyplus_path": "C:/EnergyPlus/energyplus.exe",
                    "idf_path": "energyplus/building.idf",
                    "weather_path": "energyplus/weather.epw",
                    "output_directory": "results",
                    "demo_mode": False,
                    "demo_snapshot_directory": "results/demo_snapshots",
                    "max_retry": 1,
                    "timestep_interval": 15,
                }
            ),
            encoding="utf-8",
        )
        (config_dir / "building.yaml").write_text(
            yaml.safe_dump(
                {
                    "min_temperature": 22.0,
                    "max_temperature": 25.0,
                    "min_pmv": -0.5,
                    "max_pmv": 0.5,
                    "occupancy_threshold": {"low_max": 5, "medium_max": 15},
                    "hvac_limits": {
                        "cooling_min": 22.0,
                        "cooling_max": 28.0,
                        "heating_min": 18.0,
                        "heating_max": 24.0,
                    },
                }
            ),
            encoding="utf-8",
        )
        (config_dir / "llm.yaml").write_text(
            yaml.safe_dump(
                {
                    "provider": "ollama",
                    "model": "qwen2.5",
                    "temperature": 0.2,
                    "max_tokens": 512,
                    "timeout": 60,
                }
            ),
            encoding="utf-8",
        )
