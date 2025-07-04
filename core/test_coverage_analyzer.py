from typing import Dict, List

class TestCoverageAnalyzer:
    def get_route_coverage(self, method: str, path: str) -> Dict:
        raise NotImplementedError

    def get_affected_tests(self, affected_routes: List[str]) -> List[str]:
        raise NotImplementedError

    def get_coverage_gap_report(self, contract_routes: List[str]) -> Dict:
        raise NotImplementedError
