from backend.config import ConfigManager
from backend.simulation_manager import SimulationManager
from backend.metrics import MetricsGenerator

def main():
    cfg=ConfigManager();cfg.load()
    sim=SimulationManager(cfg)

    baseline_result=sim.run_baseline()
    print(baseline_result)
    if not baseline_result.success:
        print("Baseline simulation failed; stopping before optimized run.")
        return

    optimized_result=sim.run_optimized()
    print(optimized_result)
    if not optimized_result.success:
        print("Optimized simulation failed; skipping metrics generation.")
        return

    metrics=MetricsGenerator(cfg).generate()
    print(metrics)
    print("Pipeline completed.")

if __name__=="__main__":
    main()