import time
import random
import hashlib
from typing import Optional, Dict

class ChaosSeedManager:
    def __init__(self, base_seed: Optional[int] = None):
        self.base_seed = base_seed if base_seed is not None else int(time.time())
        self.master_rng = random.Random(self.base_seed)
        self._init_subsystem_seeds()
        self.request_counter = 0

    def _init_subsystem_seeds(self):
        self.subsystem_seeds = {
            'delay': self.master_rng.randint(0, 2**32 - 1),
            'error_selection': self.master_rng.randint(0, 2**32 - 1),
            'pattern': self.master_rng.randint(0, 2**32 - 1),
            'scheduling': self.master_rng.randint(0, 2**32 - 1)
        }

        self.subsystem_rngs = {
            name: random.Random(seed) for name, seed in self.subsystem_seeds.items()
        }

    def get_rng(self, subsystem: str) -> random.Random:
        if subsystem not in self.subsystem_rngs:
            raise ValueError(f"Unknown subsystem: {subsystem}")
        return self.subsystem_rngs[subsystem]

    def get_request_seed(self, route: str, method: str, request_id: Optional[str] = None) -> int:
        if request_id:
            seed_string = f"{self.base_seed}:{route}:{method}:{request_id}"
        else:
            self.request_counter += 1
            seed_string = f"{self.base_seed}:{route}:{method}:{self.request_counter}"

        return int(hashlib.md5(seed_string.encode()).hexdigest(), 16) % (2**32)

    def get_request_rng(self, route: str, method: str, request_id: Optional[str] = None) -> random.Random:
        return random.Random(self.get_request_seed(route, method, request_id))

    def reset(self):
        self.request_counter = 0
        self._init_subsystem_seeds()

    def get_seed_info(self) -> Dict:
        return {
            "base_seed": self.base_seed,
            "request_counter": self.request_counter,
            "subsystem_seeds": self.subsystem_seeds.copy()
        }
