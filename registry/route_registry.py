# registry/route_registry.py

from typing import Optional
from contract.contract_entry import ContractEntry


class RouteMatch:
    def __init__(self, contract: ContractEntry):
        self.contract = contract


class RouteRegistry:
    def __init__(self):
        self.routes = []

    def register(self, contract: ContractEntry, use_trie: bool = False):
        """
        Registers a contract route into the registry.
        """
        self.routes.append(contract)

    def match(self, method: str, path: str) -> Optional[RouteMatch]:
        """
        Matches an incoming request against the registered contracts.

        Returns:
            RouteMatch if found, None otherwise.
        """
        for contract in self.routes:
            if contract.method.upper() == method.upper() and contract.path == path:
                return RouteMatch(contract)
        return None
