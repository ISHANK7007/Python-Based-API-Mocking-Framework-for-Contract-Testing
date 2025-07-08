from core.chaos.chaos_seed_manager import ChaosSeedManager
from core.chaos.state_store import InMemoryStateStore

class PatternBasedChaos:
    """
    Implements deterministic chaos patterns:
    - 'sequence': Triggers based on a repeated boolean sequence
    - 'nth': Every-Nth request
    - 'probabilistic': Inject with fixed probability
    - 'conditional': Based on request context
    """

    def __init__(self, pattern_config, seed_manager=None, state_store=None):
        """
        Args:
            pattern_config (dict): Defines the chaos pattern behavior
            seed_manager (ChaosSeedManager): For deterministic randomness
            state_store (StateStore): For sequence/nth tracking
        """
        self.pattern_config = pattern_config or {}
        self.seed_manager = seed_manager or ChaosSeedManager()
        self.state_store = state_store or InMemoryStateStore()

    def should_trigger(self, route, method, request_context=None) -> bool:
        """Determines if chaos should be applied for this request."""
        pattern_type = self.pattern_config.get('type')

        if pattern_type == 'sequence':
            return self._evaluate_sequence_pattern(route, method)
        elif pattern_type == 'nth':
            return self._evaluate_nth_pattern(route, method)
        elif pattern_type == 'probabilistic':
            return self._evaluate_probabilistic_pattern(route, method, request_context)
        elif pattern_type == 'conditional':
            return self._evaluate_conditional_pattern(route, method, request_context)

        return False

    def _evaluate_sequence_pattern(self, route, method) -> bool:
        key = f"{route}:{method}:sequence_index"
        sequence = self.pattern_config.get("sequence", [])
        if not sequence:
            return False

        index = self.state_store.get(key, 0)
        trigger = bool(sequence[index % len(sequence)])
        self.state_store.set(key, index + 1)
        return trigger

    def _evaluate_nth_pattern(self, route, method) -> bool:
        key = f"{route}:{method}:request_count"
        count = self.state_store.get(key, 0) + 1
        self.state_store.set(key, count)

        n = self.pattern_config.get("n", 1)
        offset = self.pattern_config.get("offset", 0)

        return (count - offset) % n == 0

    def _evaluate_probabilistic_pattern(self, route, method, request_context=None) -> bool:
        probability = self.pattern_config.get("probability", 0)
        request_id = request_context.get("id") if request_context else None
        rng = self.seed_manager.get_request_rng(route, method, request_id)
        return rng.random() < probability

    def _evaluate_conditional_pattern(self, route, method, request_context) -> bool:
        conditions = self.pattern_config.get('conditions', [])
        if not conditions or not request_context:
            return False

        for cond in conditions:
            field = cond.get('field')
            expected = cond.get('value')
            operator = cond.get('operator', 'equals')

            actual = self._extract_field_value(request_context, field)
            if not self._compare_values(actual, expected, operator):
                return False

        return True

    def _extract_field_value(self, context, field_path):
        parts = field_path.split('.')
        value = context
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    def _compare_values(self, actual, expected, operator) -> bool:
        if operator == 'equals':
            return actual == expected
        elif operator == 'not_equals':
            return actual != expected
        elif operator == 'contains':
            return isinstance(actual, str) and expected in actual
        elif operator == 'in':
            return actual in expected if isinstance(expected, (list, set)) else False
        elif operator == 'gt':
            return actual > expected
        elif operator == 'lt':
            return actual < expected
        return False

    def reset(self, route=None, method=None):
        if route is None and method is None:
            self.state_store.clear()
        else:
            prefix = f"{route or ''}:{method or ''}"
            self.state_store.clear_with_prefix(prefix)
