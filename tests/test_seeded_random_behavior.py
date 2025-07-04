import time
import random
import hashlib
from typing import Optional, Dict

class ChaosSeedManager:
    """
    Manages propagation of chaos seeds across subsystems.

    Ensures that all randomness in the chaos system is reproducible via seed injection.
    Supports subsystem-specific RNGs (e.g., delay, pattern, error) and per-request RNGs.
    """

    def __init__(self, base_seed: Optional[int] = None):
        """
        Args:
            base_seed (int): Optional seed value. Defaults to current time if not set.
        """
        self.base_seed = base_seed if base_seed is not None else int(time.time())
        self.master_rng = random.Random(self.base_seed)
        self._init_subsystem_seeds()
        self.request_counter = 0

    def _init_subsystem_seeds(self):
        """Generate unique RNGs per chaos subsystem using master RNG."""
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
        """
        Returns an RNG instance tied to a specific subsystem.

        Args:
            subsystem (str): One of ['delay', 'error_selection', 'pattern', 'scheduling']

        Raises:
            ValueError: if subsystem is not registered

        Returns:
            random.Random: Deterministic RNG for the subsystem
        """
        if subsystem not in self.subsystem_rngs:
            raise ValueError(f"Unknown subsystem: {subsystem}")
        return self.subsystem_rngs[subsystem]

    def get_request_seed(self, route: str, method: str, request_id: Optional[str] = None) -> int:
        """
        Produces a consistent seed for a request using route/method/request ID or counter.

        Args:
            route (str): API route
            method (str): HTTP method
            request_id (str): Optional request identifier

        Returns:
            int: Deterministic seed for this request
        """
        if request_id:
            seed_string = f"{self.base_seed}:{route}:{method}:{request_id}"
        else:
            self.request_counter += 1
            seed_string = f"{self.base_seed}:{route}:{method}:{self.request_counter}"

        return int(hashlib.md5(seed_string.encode()).hexdigest(), 16) % (2**32)

    def get_request_rng(self, route: str, method: str, request_id: Optional[str] = None) -> random.Random:
        """
        Returns a random generator scoped to a single request.

        Args:
            route (str)
            method (str)
            request_id (Optional[str])

        Returns:
            random.Random: RNG instance seeded per request
        """
        return random.Random(self.get_request_seed(route, method, request_id))

    def reset(self):
        """Reset internal RNG state while preserving the base seed."""
        self.request_counter = 0
        self._init_subsystem_seeds()

    def get_seed_info(self) -> Dict:
        """
        Returns metadata on seed usage for debugging/logging.

        Returns:
            dict: Seed info snapshot
        """
        return {
            "base_seed": self.base_seed,
            "request_counter": self.request_counter,
            "subsystem_seeds": self.subsystem_seeds.copy()
        }
