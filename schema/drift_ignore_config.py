from typing import Optional, Dict, Any
from contract.contract_drift_analyzer import ContractDriftAnalyzer
from core.usage_data_processor import UsageDataProcessor
from core.test_coverage_analyzer import TestCoverageAnalyzer

class UsageAwareDriftAnalyzer(ContractDriftAnalyzer):
    """
    Extended contract drift analyzer that incorporates API usage data and test coverage.
    """

    def __init__(
        self,
        old_contract_path: str,
        new_contract_path: str,
        usage_data: Optional[UsageDataProcessor] = None,
        test_coverage: Optional[TestCoverageAnalyzer] = None,
    ):
        super().__init__(old_contract_path, new_contract_path)
        self.usage_data = usage_data
        self.test_coverage = test_coverage

    def analyze_drift(self) -> Dict[str, Any]:
        diff = super().analyze_drift()

        if self.usage_data:
            diff["usage_impact"] = self._calculate_usage_impact(diff)

        if self.test_coverage:
            diff["test_impact"] = self._analyze_test_impact(diff)

        return diff

    def _calculate_usage_impact(self, diff: Dict[str, Any]) -> Dict[str, Any]:
        removed_routes = []
        modified_routes = []

        for route in diff.get("removed_routes", []):
            usage_stats = self.usage_data.get_route_usage(route["method"], route["path"])
            if usage_stats:
                removed_routes.append(self._enrich_route_with_usage(route, usage_stats))

        for route in diff.get("modified_routes", []):
            usage_stats = self.usage_data.get_route_usage(route["method"], route["path"])
            if usage_stats:
                enriched_route = self._enrich_route_with_usage(route, usage_stats)
                enriched_route["usage_stats"]["impact_score"] = self._calculate_route_impact_score(route, usage_stats)

                if "request_schema_changes" in route.get("changes", {}) and                    route["changes"]["request_schema_changes"].get("has_changes"):
                    enriched_route["parameter_impact"] = self._analyze_parameter_impact(
                        route["path"],
                        route["method"],
                        route["changes"]["request_schema_changes"],
                        usage_stats.parameter_frequencies
                    )

                modified_routes.append(enriched_route)

        affected_routes = [
            f"{r['method']}:{r['path']}" for r in diff.get("removed_routes", [])
        ] + [
            f"{r['method']}:{r['path']}" for r in diff.get("modified_routes", [])
            if self._is_breaking_change(r.get("changes", {}))
        ]

        client_impact = self.usage_data.get_client_impact(affected_routes)

        total_usage_count = sum(r["usage_stats"]["call_count"] for r in removed_routes + modified_routes)
        total_client_count = client_impact.get("affected_clients_count", 0)

        impact_score = min(100, (total_usage_count * 0.6 + total_client_count * 40)) if total_usage_count > 0 else 0

        return {
            "removed_routes_with_usage": sorted(removed_routes, key=lambda r: r["usage_stats"]["call_count"], reverse=True),
            "modified_routes_with_usage": sorted(modified_routes, key=lambda r: r["usage_stats"]["impact_score"], reverse=True),
            "client_impact": client_impact,
            "total_affected_requests": total_usage_count,
            "impact_score": round(impact_score, 2),
            "high_impact_changes": len([r for r in modified_routes if r["usage_stats"]["impact_score"] > 70]),
            "medium_impact_changes": len([r for r in modified_routes if 30 <= r["usage_stats"]["impact_score"] <= 70]),
            "low_impact_changes": len([r for r in modified_routes if r["usage_stats"]["impact_score"] < 30]),
        }

    def _enrich_route_with_usage(self, route: Dict[str, Any], usage_stats) -> Dict[str, Any]:
        enriched = route.copy()
        enriched["usage_stats"] = {
            "call_count": usage_stats.call_count,
            "unique_clients": usage_stats.unique_clients,
            "last_used": usage_stats.last_used.isoformat(),
            "success_rate": usage_stats.success_rate,
            "avg_response_time": usage_stats.avg_response_time
        }
        return enriched

    def _analyze_test_impact(self, diff: Dict[str, Any]) -> Dict[str, Any]:
        affected_routes = []
        for route in diff.get("removed_routes", []):
            route_key = f"{route['method']}:{route['path']}"
            affected_routes.append(route_key)
            coverage = self.test_coverage.get_route_coverage(route["method"], route["path"])
            if coverage:
                route["test_coverage"] = coverage

        for route in diff.get("modified_routes", []):
            if self._is_breaking_change(route.get("changes", {})):
                route_key = f"{route['method']}:{route['path']}"
                affected_routes.append(route_key)
                coverage = self.test_coverage.get_route_coverage(route["method"], route["path"])
                if coverage:
                    route["test_coverage"] = coverage

        affected_tests = self.test_coverage.get_affected_tests(affected_routes)

        all_routes = {
            f"{method.upper()}:{path}"
            for contract in [self.old_contract, self.new_contract]
            for path, path_item in contract.get("paths", {}).items()
            for method in path_item.keys()
            if method in {"get", "post", "put", "delete", "patch"}
        }

        coverage_gap = self.test_coverage.get_coverage_gap_report(list(all_routes))

        return {
            "affected_tests_count": len(affected_tests),
            "affected_tests": affected_tests[:20],
            "tests_to_update_count": len(affected_tests),
            "coverage_gap": coverage_gap,
            "high_risk_routes": [
                {
                    "path": route["path"],
                    "method": route["method"],
                    "reason": "Route will be removed but is covered by tests"
                }
                for route in diff.get("removed_routes", [])
                if "test_coverage" in route and route["test_coverage"].get("test_count", 0) > 0
            ]
        }

    def _calculate_route_impact_score(self, route: Dict[str, Any], usage_stats) -> float:
        base_score = 50 if self._is_breaking_change(route.get("changes", {})) else 20

        if usage_stats.call_count > 1000:
            base_score += 30
        elif usage_stats.call_count > 100:
            base_score += 20
        elif usage_stats.call_count > 10:
            base_score += 10

        if usage_stats.unique_clients > 10:
            base_score += 20
        elif usage_stats.unique_clients > 5:
            base_score += 10
        elif usage_stats.unique_clients > 1:
            base_score += 5

        return min(100, base_score)

    def _is_breaking_change(self, changes: Dict[str, Any]) -> bool:
        req = changes.get("request_schema_changes", {})
        if req.get("removed_properties") or req.get("required_fields_changed"):
            return True

        for status, resp in changes.get("response_changes", {}).items():
            if (resp.get("type") == "removed" and status.startswith("2")) or                (resp.get("type") == "modified" and resp.get("schema_changes", {}).get("removed_properties")):
                return True

        param_changes = changes.get("parameter_changes", {})
        if param_changes.get("removed_parameters") or param_changes.get("modified_parameters"):
            return True

        return False

    def _analyze_parameter_impact(
        self, path: str, method: str, schema_changes: Dict[str, Any], param_frequencies: Dict[str, Dict]
    ) -> Dict[str, Any]:
        impact = {
            "affected_parameters": [],
            "total_affected_usage_count": 0
        }

        for prop in schema_changes.get("removed_properties", []):
            prop_name = prop["name"]
            if prop_name in param_frequencies:
                usage_count = sum(param_frequencies[prop_name].get("values", {}).values())
                impact["affected_parameters"].append({
                    "name": prop_name,
                    "type": "removed",
                    "usage_count": usage_count,
                    "unique_values": len(param_frequencies[prop_name].get("values", {}))
                })
                impact["total_affected_usage_count"] += usage_count

        for prop in schema_changes.get("modified_properties", []):
            prop_name = prop["name"]
            old_type = prop.get("old_schema", {}).get("type")
            new_type = prop.get("new_schema", {}).get("type")
            if prop_name in param_frequencies:
                usage_count = sum(param_frequencies[prop_name].get("values", {}).values())
                sample_values = sorted(param_frequencies[prop_name].get("values", {}).items(), key=lambda x: x[1], reverse=True)[:5]
                problematic_values = [
                    {"value": val, "count": cnt}
                    for val, cnt in sample_values
                    if not self._is_value_compatible(val, old_type, new_type)
                ]
                impact["affected_parameters"].append({
                    "name": prop_name,
                    "type": "modified",
                    "old_type": old_type,
                    "new_type": new_type,
                    "usage_count": usage_count,
                    "unique_values": len(param_frequencies[prop_name].get("values", {})),
                    "problematic_values": problematic_values
                })
                impact["total_affected_usage_count"] += sum(v["count"] for v in problematic_values)

        return impact

    def _is_value_compatible(self, value: str, old_type: str, new_type: str) -> bool:
        if old_type == new_type:
            return True
        try:
            if new_type == "string":
                return True
            if new_type == "number":
                float(value)
                return True
            if new_type == "integer":
                int(value)
                return True
            if new_type == "boolean":
                return value.lower() in {"true", "false", "1", "0"}
        except Exception:
            return False
        return False
