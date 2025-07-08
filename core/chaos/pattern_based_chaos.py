from chaos.state_store import InMemoryStateStore

class PatternBasedChaos:
    """
    Implements deterministic chaos patterns that follow specific sequences.

    Supported pattern types:
    - 'sequence': Repeats a boolean list (e.g., [False, False, True])
    - 'nth': Triggers chaos every nth request (e.g., every 3rd)
    - 'conditional': Evaluates context-based conditions
    """

    def __init__(self, pattern_config, state_store=None):
        """
        Initialize with pattern configuration.

        Args:
            pattern_config (dict): Configuration defining the pattern behavior
            state_store (StateStore): Optional store (defaults to in-memory)
        """
        self.pattern_config = pattern_config
        self.state_store = state_store or InMemoryStateStore()

    def should_trigger(self, route, method, request_context=None):
        """Determine if chaos should trigger for this request."""
        pattern_type = self.pattern_config.get('type')

        if pattern_type == 'sequence':
            return self._evaluate_sequence_pattern(route, method)
        elif pattern_type == 'nth':
            return self._evaluate_nth_pattern(route, method)
        elif pattern_type == 'conditional':
            return self._evaluate_conditional_pattern(route, method, request_context)

        return False

    def _evaluate_sequence_pattern(self, route, method):
        key = f"{route}:{method}:sequence_index"
        index = self.state_store.get(key, 0)
        sequence = self.pattern_config.get('sequence', [])

        if not sequence:
            return False

        should_trigger = bool(sequence[index % len(sequence)])
        self.state_store.set(key, (index + 1) % len(sequence))
        return should_trigger

    def _evaluate_nth_pattern(self, route, method):
        key = f"{route}:{method}:request_count"
        count = self.state_store.get(key, 0) + 1
        self.state_store.set(key, count)

        n = self.pattern_config.get('n', 1)
        offset = self.pattern_config.get('offset', 0)

        return (count - offset) % n == 0

    def _evaluate_conditional_pattern(self, route, method, request_context):
        conditions = self.pattern_config.get('conditions', [])
        if not conditions or not request_context:
            return False

        for condition in conditions:
            field = condition.get('field', '')
            expected = condition.get('value')
            operator = condition.get('operator', 'equals')

            actual = self._extract_field_value(request_context, field)
            if not self._compare_values(actual, expected, operator):
                return False

        return True

    def _extract_field_value(self, context, field_path):
        """Extract nested value from dict using dot notation (e.g., headers.User-Agent)."""
        parts = field_path.split(".")
        value = context
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    def _compare_values(self, actual, expected, operator):
        """Compare values based on operator."""
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
        """
        Reset pattern state.

        Args:
            route: Optional route to reset (None = all)
            method: Optional method to reset (None = all)
        """
        if route is None and method is None:
            self.state_store.clear()
        else:
            prefix = f"{route or ''}:{method or ''}"
            self.state_store.clear_with_prefix(prefix)
