from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json, shutil, subprocess, time
from backend.config import ConfigManager,get_logger
from backend.collector import RawBuildingState
from backend.rule_engine import RuleEngine
from backend.validator import ActionValidator, ValidatedAction
from backend.controller import ActuatorController
from llm.agent import LLMAgent

logger=get_logger("simulation_manager")

SUMMARY_FILENAME="simulation_summary.json"

BASELINE_COOLING_SETPOINT_C=22.0
BASELINE_HEATING_SETPOINT_C=21.0
COOLING_SAVINGS_PER_DEGREE=0.06
HEATING_SAVINGS_PER_DEGREE=0.05
MAX_HVAC_REDUCTION=0.6
COMFORT_NEUTRAL_TEMPERATURE_C=23.5
PMV_PER_DEGREE=0.3


DEFAULT_BASELINE_METRICS={
    "sample_count":1,
    "hvac_energy_kwh":150.0,
    "total_energy_kwh":210.0,
    "average_temperature":24.5,
    "average_pmv":0.4,
}

@dataclass
class SimulationResult:
    success: bool
    duration_seconds: float
    output_directory: Path
    exit_code: int
    warnings: list[str]=field(default_factory=list)
    error_message: str|None=None

class SimulationManager:

    def __init__(self,config:ConfigManager)->None:
        self.cfg=config
        self.sim=self.cfg.simulation

    def validate_environment(self)->None:
        exe=self.sim.energyplus_path
        if not exe.exists():
            raise FileNotFoundError(f"EnergyPlus executable not found: {exe}")
        for p,name in [(self.sim.idf_path,"IDF"),(self.sim.weather_path,"Weather")]:
            if not p.exists():
                raise FileNotFoundError(f"{name} file not found: {p}")
        self.sim.output_directory.mkdir(parents=True,exist_ok=True)

    def clean_previous_results(self)->None:
        self._clean_directory(self.sim.output_directory/"baseline")

    def _clean_directory(self,out:Path)->None:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True,exist_ok=True)

    def _load_demo_states(self)->list[RawBuildingState]:
        
        snap_dir=Path(self.sim.demo_snapshot_directory)
        files=sorted(snap_dir.glob("*.json"))
        if not files:
            raise FileNotFoundError(f"No demo snapshots found in {snap_dir}")
        states=[]
        for f in files:
            data=json.loads(f.read_text(encoding="utf-8"))
            states.append(RawBuildingState(**data))
        return states

    def _default_state(self)->RawBuildingState:
        
        b=self.cfg.building
        mid_temp=(b.min_temperature+b.max_temperature)/2.0
        return RawBuildingState(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            zone_temperature=mid_temp,
            humidity=45.0,
            occupancy=self.cfg.building.occupancy_threshold.medium_max,
            hvac_energy=180.0,
            lighting_energy=40.0,
            pmv=0.2,
        )

    def _collect_states(self)->list[RawBuildingState]:
        
        try:
            return self._load_demo_states()
        except FileNotFoundError:
            logger.info("No demo snapshots found - using default synthetic reading for metrics estimation.")
            return [self._default_state()]

    @staticmethod
    def _aggregate_states(states:list[RawBuildingState])->dict:
        
        count=len(states)
        hvac_energy=sum(s.hvac_energy for s in states)
        total_energy=sum(s.hvac_energy+s.lighting_energy for s in states)
        avg_temp=sum(s.zone_temperature for s in states)/count
        avg_pmv=sum(s.pmv for s in states)/count
        return {
            "sample_count":count,
            "hvac_energy_kwh":hvac_energy,
            "total_energy_kwh":total_energy,
            "average_temperature":avg_temp,
            "average_pmv":avg_pmv,
        }

    def _estimate_baseline_metrics(self,states:list[RawBuildingState])->dict:

        if not states:
            return dict(DEFAULT_BASELINE_METRICS)
        return self._aggregate_states(states)

    def _run_ai_loop(self,states:list[RawBuildingState])->list[ValidatedAction]:
        
        rules=RuleEngine(self.cfg)
        agent=LLMAgent(self.cfg)
        validator=ActionValidator(self.cfg)
        controller=ActuatorController(self.cfg)

        actions=[]
        for state in states:
            features=rules.process(state)
            action=agent.decide(features)
            validated=validator.validate(action)
            controller.apply(validated)
            actions.append(validated)
        return actions

    def _estimate_optimized_metrics(self,states:list[RawBuildingState],actions:list[ValidatedAction])->dict:
        
        if not states or not actions:
            return dict(DEFAULT_BASELINE_METRICS)

        count=len(states)
        total_hvac=0.0
        total_lighting=0.0
        temp_sum=0.0
        pmv_sum=0.0

        for state,action in zip(states,actions):
            cooling_relief=max(0.0,action.cooling_setpoint-BASELINE_COOLING_SETPOINT_C)
            heating_relief=max(0.0,BASELINE_HEATING_SETPOINT_C-action.heating_setpoint)
            hvac_reduction=min(
                MAX_HVAC_REDUCTION,
                cooling_relief*COOLING_SAVINGS_PER_DEGREE+heating_relief*HEATING_SAVINGS_PER_DEGREE,
            )
            total_hvac+=state.hvac_energy*(1.0-hvac_reduction)
            total_lighting+=state.lighting_energy*(action.lighting_level/100.0)

            est_temp=(action.cooling_setpoint+action.heating_setpoint)/2.0
            temp_sum+=est_temp
            pmv_sum+=(est_temp-COMFORT_NEUTRAL_TEMPERATURE_C)*PMV_PER_DEGREE

        return {
            "sample_count":count,
            "hvac_energy_kwh":total_hvac,
            "total_energy_kwh":total_hvac+total_lighting,
            "average_temperature":temp_sum/count,
            "average_pmv":pmv_sum/count,
        }

    @staticmethod
    def _actions_to_dicts(actions:list[ValidatedAction])->list[dict]:
        return [
            {
                "cooling_setpoint":a.cooling_setpoint,
                "heating_setpoint":a.heating_setpoint,
                "lighting_level":a.lighting_level,
                "corrections":a.corrections,
            }
            for a in actions
        ]

    def _build_optimized_recommendations(self,actions:list[ValidatedAction])->list[str]:
        if not actions:
            return ["No AI actions were available to generate recommendations for."]

        avg_cool=sum(a.cooling_setpoint for a in actions)/len(actions)
        avg_heat=sum(a.heating_setpoint for a in actions)/len(actions)
        avg_light=sum(a.lighting_level for a in actions)/len(actions)

        recommendations=[
            f"AI selected an average cooling setpoint of {avg_cool:.1f} C and heating setpoint of "
            f"{avg_heat:.1f} C to reduce HVAC load while remaining within configured comfort limits.",
            f"AI reduced average lighting output to {avg_light:.0f}% of maximum to save lighting energy.",
        ]
        if any(a.corrections for a in actions):
            recommendations.append(
                "The validator adjusted one or more AI-proposed setpoints to stay within configured HVAC safety limits."
            )
        return recommendations

    def _is_comfort_maintained(self,average_temperature:float)->bool:
        b=self.cfg.building
        return b.min_temperature<=average_temperature<=b.max_temperature

    def _write_summary(
        self,
        mode:str,
        output_dir:Path,
        metrics:dict,
        success:bool,
        duration:float,
        applied_actions:list[dict]|None=None,
        ai_recommendations:list[str]|None=None,
    )->Path:

        average_temperature=round(metrics.get("average_temperature",0.0),4)
        summary={
            "mode":mode,
            "success":success,
            "runtime_seconds":round(duration,3),
            "timestamp":datetime.now().isoformat(timespec="seconds"),
            "sample_count":metrics.get("sample_count",0),
            "total_energy_kwh":round(metrics.get("total_energy_kwh",0.0),4),
            "hvac_energy_kwh":round(metrics.get("hvac_energy_kwh",0.0),4),
            "average_temperature":average_temperature,
            "average_pmv":round(metrics.get("average_pmv",0.0),4),
            "comfort_maintained":self._is_comfort_maintained(average_temperature),
            "applied_actions":applied_actions or [],
            "ai_recommendations":ai_recommendations or [],
        }
        output_dir.mkdir(parents=True,exist_ok=True)
        summary_path=output_dir/SUMMARY_FILENAME
        with summary_path.open("w",encoding="utf-8") as fh:
            json.dump(summary,fh,indent=2)
        logger.info("Wrote simulation summary to %s",summary_path)
        return summary_path

    def run_baseline(self,timeout:int=600)->SimulationResult:
        out=self.sim.output_directory/"baseline"

        if self.sim.demo_mode:
            logger.info("Demo mode enabled - skipping EnergyPlus subprocess execution for baseline run.")
            out.mkdir(parents=True,exist_ok=True)
            states=self._load_demo_states()
            metrics=self._aggregate_states(states)
            self._write_summary(
                "baseline",out,metrics,True,0.0,
                applied_actions=[],
                ai_recommendations=["Baseline metrics derived from recorded demo snapshots (no AI control applied)."],
            )
            return SimulationResult(
                True,
                0.0,
                out,
                0,
                warnings=["Demo mode: EnergyPlus execution skipped."],
            )

        self.validate_environment()
        self.clean_previous_results()
        cmd=[str(self.sim.energyplus_path),"-w",str(self.sim.weather_path),"-d",str(out),str(self.sim.idf_path)]
        start=time.perf_counter()
        try:
            proc=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
        except subprocess.TimeoutExpired:
            return SimulationResult(False,time.perf_counter()-start,out,-1,error_message="Simulation timed out")
        except Exception as e:
            return SimulationResult(False,time.perf_counter()-start,out,-1,error_message=str(e))
        duration=time.perf_counter()-start
        warnings=[]
        err=out/"eplusout.err"
        fatal=False
        if err.exists():
            txt=err.read_text(errors="ignore")
            if "Warning" in txt:
                warnings.append("EnergyPlus warnings present.")
            fatal="** Fatal **" in txt or "Fatal" in txt
        else:
            fatal=True
            warnings.append("eplusout.err missing.")
        success=proc.returncode==0 and err.exists() and not fatal
        if success:
            warnings.append(
                "Metrics estimated from recorded demo snapshots (or reasonable defaults); "
                "EnergyPlus output parsing is out of scope for this MVP."
            )
            states=self._collect_states()
            metrics=self._estimate_baseline_metrics(states)
            self._write_summary(
                "baseline",out,metrics,True,duration,
                applied_actions=[],
                ai_recommendations=["Baseline metrics derived from recorded demo snapshots (no AI control applied)."],
            )
        return SimulationResult(success,duration,out,proc.returncode,warnings,None if success else "Simulation failed")

    def run_optimized(self,timeout:int=600)->SimulationResult:
        out=self.sim.output_directory/"optimized"

        if self.sim.demo_mode:
            logger.info("Demo mode enabled - running AI closed loop over demo snapshots for optimized run.")
            out.mkdir(parents=True,exist_ok=True)
            states=self._load_demo_states()
            actions=self._run_ai_loop(states)
            metrics=self._estimate_optimized_metrics(states,actions)
            self._write_summary(
                "optimized",out,metrics,True,0.0,
                applied_actions=self._actions_to_dicts(actions),
                ai_recommendations=self._build_optimized_recommendations(actions),
            )
            return SimulationResult(
                True,
                0.0,
                out,
                0,
                warnings=["Demo mode: AI closed loop executed over recorded snapshots."],
            )

        self.validate_environment()
        self._clean_directory(out)
        cmd=[str(self.sim.energyplus_path),"-w",str(self.sim.weather_path),"-d",str(out),str(self.sim.idf_path)]
        start=time.perf_counter()
        try:
            proc=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
        except subprocess.TimeoutExpired:
            return SimulationResult(False,time.perf_counter()-start,out,-1,error_message="Simulation timed out")
        except Exception as e:
            return SimulationResult(False,time.perf_counter()-start,out,-1,error_message=str(e))
        duration=time.perf_counter()-start
        warnings=[]
        err=out/"eplusout.err"
        fatal=False
        if err.exists():
            txt=err.read_text(errors="ignore")
            if "Warning" in txt:
                warnings.append("EnergyPlus warnings present.")
            fatal="** Fatal **" in txt or "Fatal" in txt
        else:
            fatal=True
            warnings.append("eplusout.err missing.")
        success=proc.returncode==0 and err.exists() and not fatal
        if success:
            warnings.append(
                "Metrics estimated from validated AI actions applied to recorded demo snapshots (or reasonable "
                "defaults); EnergyPlus output parsing is out of scope for this MVP."
            )
            states=self._collect_states()
            actions=self._run_ai_loop(states)
            metrics=self._estimate_optimized_metrics(states,actions)
            self._write_summary(
                "optimized",out,metrics,True,duration,
                applied_actions=self._actions_to_dicts(actions),
                ai_recommendations=self._build_optimized_recommendations(actions),
            )
        return SimulationResult(success,duration,out,proc.returncode,warnings,None if success else "Simulation failed")