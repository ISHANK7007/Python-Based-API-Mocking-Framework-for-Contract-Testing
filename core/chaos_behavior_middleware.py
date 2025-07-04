import time
from chaos.pattern_based_chaos import PatternBasedChaos
from chaos.seeded_random_behavior import SeededRandomBehavior
from chaos.state_store import InMemoryStateStore
from core.chaos_engine import ChaosEngine
from core.chaos_profile_resolver import ChaosProfileResolver

class ChaosBehaviorMiddleware:
    """
    Middleware that applies chaos behavior (delay, error, patterns) to mock responses
    based on route, method, and request context.
    """

    def __init__(self, chaos_config, profile_resolver=None, chaos_engine=None,
                 time_provider=None, state_store=None, recorder=None, seed=None):
        self.chaos_config = chaos_config or {}
        self.profile_resolver = profile_resolver or ChaosProfileResolver(self.chaos_config)
        self.chaos_engine = chaos_engine or ChaosEngine()
        self.time_provider = time_provider or time.time
        self.state_store = state_store or InMemoryStateStore()
        self.recorder = recorder

        self.pattern_chaos = PatternBasedChaos({}, self.state_store)
        self.seeded_random = SeededRandomBehavior(seed, self.state_store)

    def apply(self, route, method, response_generator_fn):
        """
        Wrap the response generator with chaos behavior injection.

        Args:
            route (str): API route (e.g., /cart)
            method (str): HTTP method
            response_generator_fn (callable): Function returning the response

        Returns:
            callable: A wrapped function that may inject chaos
        """
        def chaos_wrapped_generator(*args, **kwargs):
            request_context = kwargs.get('request_context', {})
            request_id = request_context.get('id')

            chaos_settings = self._get_effective_chaos_settings(route, method)

            if not chaos_settings.get('enabled', False):
                return response_generator_fn(*args, **kwargs)

            # Pattern-based behavior (e.g., timeout_burst)
            if 'pattern' in chaos_settings:
                self.pattern_chaos.pattern_config = chaos_settings['pattern']
                if self.pattern_chaos.should_trigger(route, method, request_context):
                    error_response = chaos_settings.get('error_response') or {
                        "status_code": 500,
                        "body": {"error": "Internal Server Error"}
                    }
                    if self.recorder:
                        self.recorder.record_error(error_response, route, method)
                    return error_response

            # Probabilistic error injection
            if 'error_ratio' in chaos_settings:
                rng = self.seeded_random.get_random_for_request(route, method, request_id)
                if rng.random() < chaos_settings.get('error_ratio', 0):
                    error_response = self._generate_error_response(chaos_settings, rng)
                    if self.recorder:
                        self.recorder.record_error(error_response, route, method)
                    return error_response

            # Get the normal response
            response = response_generator_fn(*args, **kwargs)

            # Chaos delay logic
            delay_ms = self._calculate_delay(chaos_settings, route, method, request_id)
            if delay_ms > 0:
                if self.recorder:
                    self.recorder.record_delay(delay_ms, route, method)
                time.sleep(delay_ms / 1000.0)

            return response

        return chaos_wrapped_generator

    def _calculate_delay(self, chaos_settings, route, method, request_id=None):
        """Calculate delay in milliseconds, optionally randomized and capped."""
        delay_config = chaos_settings.get('delay_ms')
        if not delay_config:
            return 0

        if isinstance(delay_config, int):
            return delay_config

        rng = self.seeded_random.get_random_for_request(route, method, request_id)
        return self.chaos_engine.calculate_delay(delay_config, rng)

    def _generate_error_response(self, chaos_settings, rng):
        """
        Generate a chaos-induced error response.

        Args:
            chaos_settings (dict): Chaos config for route
            rng (random.Random): Seeded RNG for reproducibility

        Returns:
            dict: Error response structure
        """
        status_code = chaos_settings.get("status_code", 503)
        body = chaos_settings.get("error_body", {"error": "Injected Chaos Error"})
        return {
            "status_code": status_code,
            "body": body
        }

    def _get_effective_chaos_settings(self, route, method):
        """
        Resolve and return chaos settings for this route and method.

        Returns:
            dict: Effective chaos configuration
        """
        return self.profile_resolver.resolve(route, method)
