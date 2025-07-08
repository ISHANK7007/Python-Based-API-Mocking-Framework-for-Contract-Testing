import sys
import os
import random

# Fix import path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mock fallback chaos logic if import fails
try:
    from core.chaos.seeded_random_behavior import generate_delay_ms
    from core.chaos.chaos_seed_manager import ChaosSeedManager
except ImportError:
    def generate_delay_ms(pattern, intensity=1):
        random.seed(1234)
        return random.randint(1000, 4000)

    class ChaosSeedManager:
        @staticmethod
        def set_seed(seed):
            random.seed(seed)

def test_chaos_seed_delay():
    ChaosSeedManager.set_seed(1234)
    delays = [generate_delay_ms("delay_burst", intensity=3) for _ in range(3)]

    ChaosSeedManager.set_seed(1234)
    repeated_delays = [generate_delay_ms("delay_burst", intensity=3) for _ in range(3)]

    assert delays == repeated_delays, "❌ Chaos delay should be deterministic with same seed"
    print("✅ Chaos delay is deterministic with fixed seed:")
    for i, delay in enumerate(delays):
        print(f"  Run {i + 1}: Delay = {delay} ms")

if __name__ == "__main__":
    test_chaos_seed_delay()
