class ChaosEngine:
    def __init__(self, max_delay_ms=5000):
        self.max_delay_ms = max_delay_ms

    def calculate_delay(self, delay_config, rng):
        """
        Supports:
        - int: fixed delay
        - dict: { "min": X, "max": Y } random delay within range
        """
        if isinstance(delay_config, int):
            return min(delay_config, self.max_delay_ms)

        if isinstance(delay_config, dict):
            min_ms = delay_config.get("min", 0)
            max_ms = delay_config.get("max", self.max_delay_ms)
            value = rng.randint(min_ms, max_ms)
            return min(value, self.max_delay_ms)

        return 0
