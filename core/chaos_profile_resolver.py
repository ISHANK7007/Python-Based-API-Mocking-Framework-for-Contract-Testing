class ChaosProfileResolver:
    def __init__(self, chaos_config):
        self.chaos_config = chaos_config or {}

    def resolve(self, route, method):
        """
        Resolves chaos settings from config using route/method key.

        Returns:
            dict: chaos profile for the request (e.g., delay_ms, error_ratio, pattern)
        """
        return self.chaos_config.get(f"{method.upper()} {route}", {})
