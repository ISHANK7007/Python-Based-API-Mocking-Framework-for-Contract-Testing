from contract.contract_entry import ContractEntry
from typing import List, Tuple

class ContractDiffer:
    """
    Compares two sets of ContractEntry objects and reports breaking and non-breaking changes.
    """

    def __init__(self, from_contracts: List[ContractEntry], to_contracts: List[ContractEntry]):
        self.from_contracts = from_contracts
        self.to_contracts = to_contracts

    def compute_diff(self) -> Tuple[List[str], List[str]]:
        """
        Returns:
            breaking_changes: List of strings describing breaking changes.
            non_breaking_changes: List of strings describing non-breaking changes.
        """
        breaking_changes = []
        non_breaking_changes = []

        from_paths = {f"{e.method.value} {e.path}" for e in self.from_contracts}
        to_paths = {f"{e.method.value} {e.path}" for e in self.to_contracts}

        removed_routes = from_paths - to_paths
        added_routes = to_paths - from_paths

        for removed in removed_routes:
            breaking_changes.append(f"Removed endpoint: {removed}")

        for added in added_routes:
            non_breaking_changes.append(f"Added endpoint: {added}")

        return breaking_changes, non_breaking_changes
