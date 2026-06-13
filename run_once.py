"""Run the full WorldPulse pipeline ONCE (manual trigger, no scheduler)."""
from scheduler import run_pipeline

if __name__ == "__main__":
    print("=== WorldPulse — One-shot pipeline ===\n")
    run_pipeline()
    print("\n=== Done ===")
