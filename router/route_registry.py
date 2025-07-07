import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from collections import defaultdict

from contract.contract_entry import ContractEntry, HttpMethod

logger = logging.getLogger(__name__)


@dataclass
class RouteMatch:
    """Represents a matched route with extracted parameters"""
    contract: ContractEntry
    path_params: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    match_type: str = "exact"  # "exact", "wildcard", or "parameterized"
    match_score: int = 100     # Higher is better/more specific match


class RouteRegistry:
    """Registers and matches API routes with support for parameterized and wildcard paths."""

    def __init__(self):
        self._routes_by_method: Dict[HttpMethod, List[ContractEntry]] = defaultdict(list)
        self._pattern_cache: Dict[str, re.Pattern] = {}

        self._total_routes = 0
        self._static_routes = 0
        self._parameterized_routes = 0
        self._wildcard_routes = 0

    @property
    def total_routes(self) -> int:
        return self._total_routes

    def _compile_path_pattern(self, path: str) -> re.Pattern:
        if path in self._pattern_cache:
            return self._pattern_cache[path]

        if "*" in path:
            pattern_str = "^" + re.escape(path).replace("\\*", ".*") + "$"
        else:
            pattern_str = re.sub(r"{([^{}]+)}", r"(?P<\1>[^/]+)", path)
            pattern_str = "^" + pattern_str + "$"

        compiled = re.compile(pattern_str)
        self._pattern_cache[path] = compiled
        return compiled

    def _categorize_path(self, path: str) -> Tuple[str, int]:
        if "*" in path:
            return "wildcard", 10
        elif "{" in path:
            segments = path.strip("/").split("/")
            param_count = len(re.findall(r"{([^{}]+)}", path))
            static_count = len(segments) - param_count
            score = 50 + static_count * 10 - param_count
            return "parameterized", score
        else:
            return "static", 100

    def register(self, contract: ContractEntry) -> None:
        path = contract.path
        method = contract.method

        self._compile_path_pattern(path)
        self._routes_by_method[method].append(contract)

        self._total_routes += 1
        category, _ = self._categorize_path(path)

        if category == "static":
            self._static_routes += 1
        elif category == "parameterized":
            self._parameterized_routes += 1
        elif category == "wildcard":
            self._wildcard_routes += 1

        logger.debug(f"Registered route: {method.value} {path} ({category})")

    def register_many(self, contracts: List[ContractEntry]) -> None:
        for contract in contracts:
            self.register(contract)

        logger.info(f"Registered {len(contracts)} routes: "
                    f"{self._static_routes} static, "
                    f"{self._parameterized_routes} parameterized, "
                    f"{self._wildcard_routes} wildcard")

    def match(self, method: Union[str, HttpMethod], path: str) -> Optional[RouteMatch]:
        if isinstance(method, str):
            try:
                method = HttpMethod(method.upper())
            except ValueError:
                return None

        routes = self._routes_by_method.get(method, [])
        if not routes:
            return None

        for contract in routes:
            if contract.path == path:
                return RouteMatch(contract=contract, match_type="exact", match_score=100)

        matches = []

        for contract in routes:
            category, score = self._categorize_path(contract.path)
            pattern = self._pattern_cache.get(contract.path)

            if not pattern:
                continue

            match = pattern.match(path)
            if match:
                path_params = match.groupdict() if category == "parameterized" else {}
                matches.append(RouteMatch(
                    contract=contract,
                    path_params=path_params,
                    match_type=category,
                    match_score=score
                ))

        return max(matches, key=lambda m: m.match_score) if matches else None

    def find_all_matches(self, method: Union[str, HttpMethod], path: str) -> List[RouteMatch]:
        if isinstance(method, str):
            try:
                method = HttpMethod(method.upper())
            except ValueError:
                return []

        routes = self._routes_by_method.get(method, [])
        matches = []

        for contract in routes:
            category, score = self._categorize_path(contract.path)
            pattern = self._pattern_cache.get(contract.path)

            if contract.path == path:
                matches.append(RouteMatch(contract=contract, match_type="exact", match_score=100))
                continue

            if pattern and pattern.match(path):
                path_params = pattern.match(path).groupdict() if category == "parameterized" else {}
                matches.append(RouteMatch(
                    contract=contract,
                    path_params=path_params,
                    match_type=category,
                    match_score=score
                ))

        return sorted(matches, key=lambda m: m.match_score, reverse=True)

    def get_routes(self, method: Optional[HttpMethod] = None) -> List[ContractEntry]:
        if method:
            return list(self._routes_by_method.get(method, []))

        all_routes = []
        for route_list in self._routes_by_method.values():
            all_routes.extend(route_list)
        return all_routes

    def clear(self) -> None:
        self._routes_by_method.clear()
        self._pattern_cache.clear()
        self._total_routes = 0
        self._static_routes = 0
        self._parameterized_routes = 0
        self._wildcard_routes = 0
