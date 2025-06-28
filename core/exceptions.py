class ConditionEvaluationError(Exception):
    """Raised when a condition string cannot be evaluated or compiled."""
    pass

class ContractLoadError(Exception):
    """Raised when a contract fails to load properly."""
    pass
