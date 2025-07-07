import time
import random
import hashlib
from chaos.state_store import InMemoryStateStore

class SeededRandomBehavior:
    """
    Provides reproducible random behavior based on a base seed.

    This supports deterministic chaos injection that can be exactly replayed
    across test runs using the same seed.
    """

    def __init__(self, seed: int = None, state_store=None):
        """
        Initialize with an optional seed and a state store.

        Args:
            seed (int): Optional seed value. If None, uses current timestamp.
            state_store (StateStore): Optional persistent counter store.
        """
        self.base_seed = seed if seed is not None else int(time.time())
        self.state_store = state_store or InMemoryStateStore()

    def get_random_for_request(self, route: str, method: str, request_id: str = None) -> random.Random:
        """
        Get a deterministic random generator for a specific request.

        Args:
            route (str): The request path (e.g., /cart)
            method (str): HTTP method (e.g., GET, POST)
            request_id (str): Optional UUID or stable ID for the request

        Returns:
            random.Random: Seeded random generator instance
        """
        if request_id:
            seed = self._hash_seed(f"{self.base_seed}:{route}:{method}:{request_id}")
        else:
            key = f"{route}:{method}:request_counter"
            counter = self.state_store.get(key, 0)
            self.state_store.set(key, counter + 1)
            seed = self._hash_seed(f"{self.base_seed}:{route}:{method}:{counter}")

        return random.Random(seed)

    def _hash_seed(self, seed_string: str) -> int:
        """
        Hash a string into a 32-bit integer seed.

        Args:
            seed_string (str): String to hash

        Returns:
            int: Deterministic numeric seed
        """
        return int(hashlib.md5(seed_string.encode()).hexdigest(), 16) % (2**32)

    def set_seed(self, seed: int):
        """
        Override the base seed.

        Args:
            seed (int): New seed to use

        Returns:
            self
        """
        self.base_seed = seed
        return self
