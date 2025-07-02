from contract.compatibility_checker import ContractCompatibilityChecker, CompatibilityResult
from contract.contract_entry import ContractEntry
from core.diff_severity_grouping import Severity


def check_compatibility(self,
                        contract1: ContractEntry,
                        contract2: ContractEntry,
                        ignore_non_breaking: bool = True,
                        severity_threshold: Severity = Severity.HIGH) -> CompatibilityResult:
    """
    Check compatibility between two contracts.

    Args:
        contract1: The original contract
        contract2: The new contract to check compatibility with
        ignore_non_breaking: If True, only breaking changes affect compatibility
        severity_threshold: Minimum severity level to consider incompatible

    Returns:
        CompatibilityResult with assessment and reasons
    """
    # Directly instantiate the core checker
    checker = ContractCompatibilityChecker()

    return checker.check_compatibility(
        old_contract=contract1,
        new_contract=contract2,
        ignore_non_breaking=ignore_non_breaking,
        severity_threshold=severity_threshold
    )
