from dataclasses import dataclass
from typing import Dict, List, Any, Set, Optional, Tuple
import os

from contract.contract_loader import ContractLoader
from contract.contract_entry import ContractEntry
from contract.contract_diff_formatter import EnhancedDiffFormatter
from core.diff_runner import EnhancedContractDiffer
from core.diff_severity_grouping import SeverityGroupedFormatter, Severity
from contract.contract_diff_types import ChangeSummary, ChangeType


class CompatibilityResult(Tuple):
    """Result of a compatibility check between two API contracts."""
    is_compatible: bool
    incompatible_routes: List[Dict[str, Any]]
    incompatible_fields: List[Dict[str, Any]]
    incompatible_responses: List[Dict[str, Any]]
    compatibility_details: Dict[str, Any]

    def __bool__(self):
        return self.is_compatible

    @property
    def incompatibility_count(self) -> int:
        return len(self.incompatible_routes) + len(self.incompatible_fields) + len(self.incompatible_responses)

    @property
    def reasons(self) -> List[str]:
        reasons = []
        for route in self.incompatible_routes:
            reasons.append(f"Route incompatibility: {route['description']}")
        for field in self.incompatible_fields:
            reasons.append(f"Field incompatibility: {field['description']}")
        for response in self.incompatible_responses:
            reasons.append(f"Response incompatibility: {response['description']}")
        return reasons


class ContractCompatibilityChecker:
    def __init__(self):
        self.differ = EnhancedContractDiffer()

    def check_compatibility(
        self,
        old_contract: ContractEntry,
        new_contract: ContractEntry,
        ignore_non_breaking: bool = True,
        severity_threshold: Severity = Severity.HIGH
    ) -> CompatibilityResult:
        diff_result = self.differ.diff_contracts(old_contract, new_contract)
        formatter = EnhancedDiffFormatter()
        summaries = formatter.generate_change_summaries(diff_result)

        filtered_summaries = self._filter_summaries(summaries, ignore_non_breaking, severity_threshold)

        incompatible_routes = []
        incompatible_fields = []
        incompatible_responses = []

        for summary in filtered_summaries:
            incompatibility = {
                'path': summary.path,
                'method': summary.method,
                'description': summary.get_summary_text().replace('[BREAKING] ', ''),
                'severity': SeverityGroupedFormatter.map_change_to_severity(summary).value,
                'details': summary.details
            }

            if summary.change_type in [ChangeType.ROUTE_REMOVED, ChangeType.ROUTE_MODIFIED]:
                incompatible_routes.append(incompatibility)
            elif summary.change_type in [
                ChangeType.REQUEST_FIELD_REMOVED,
                ChangeType.REQUEST_FIELD_MODIFIED,
                ChangeType.REQUEST_FIELD_NEWLY_REQUIRED
            ]:
                incompatible_fields.append(incompatibility)
            elif summary.change_type in [
                ChangeType.RESPONSE_STATUS_REMOVED,
                ChangeType.RESPONSE_FIELD_REMOVED,
                ChangeType.RESPONSE_FIELD_MODIFIED,
                ChangeType.RESPONSE_CONTENT_TYPE_CHANGED
            ]:
                incompatible_responses.append(incompatibility)

        is_compatible = not (incompatible_routes or incompatible_fields or incompatible_responses)
        compatibility_details = self._extract_compatibility_details(diff_result)

        return CompatibilityResult(
            is_compatible,
            incompatible_routes,
            incompatible_fields,
            incompatible_responses,
            compatibility_details
        )

    def _filter_summaries(
        self,
        summaries: List[ChangeSummary],
        ignore_non_breaking: bool,
        severity_threshold: Severity
    ) -> List[ChangeSummary]:
        filtered = []
        for summary in summaries:
            if ignore_non_breaking and not summary.is_breaking:
                continue
            severity = SeverityGroupedFormatter.map_change_to_severity(summary)
            if self._severity_below_threshold(severity, severity_threshold):
                continue
            filtered.append(summary)
        return filtered

    def _severity_below_threshold(self, severity: Severity, threshold: Severity) -> bool:
        order = {Severity.HIGH: 3, Severity.MEDIUM: 2, Severity.LOW: 1, Severity.INFO: 0}
        return order.get(severity, 0) < order.get(threshold, 0)

    def _extract_compatibility_details(self, diff_result: Dict[str, Any]) -> Dict[str, Any]:
        details = {
            'schema_compatibility': {},
            'response_compatibility': {}
        }

        for path, route_details in diff_result.get('detailed_diffs', {}).items():
            schema_diff = route_details.get('request_schema')
            if schema_diff and hasattr(schema_diff, 'is_backwards_compatible'):
                details['schema_compatibility'][path] = {
                    'is_backwards_compatible': schema_diff.is_backwards_compatible,
                    'compatibility_impact': getattr(schema_diff, 'compatibility_impact', 'unknown')
                }

            response_diff = route_details.get('responses')
            if response_diff and hasattr(response_diff, 'response_compatibility'):
                details['response_compatibility'][path] = {
                    'has_breaking_changes': getattr(response_diff, 'has_breaking_response_changes', False),
                    'status_codes': {}
                }
                for code, info in getattr(response_diff, 'response_compatibility', {}).items():
                    details['response_compatibility'][path]['status_codes'][code] = {
                        'is_backwards_compatible': info.get('is_backwards_compatible', True)
                    }

        return details


def compatibility_check(
    old_file: str,
    new_file: str,
    ignore_non_breaking: bool = True,
    severity_threshold: str = "HIGH"
) -> Tuple[bool, List[str], Dict[str, Any]]:
    if not os.path.exists(old_file):
        raise FileNotFoundError(f"Source file '{old_file}' not found")
    if not os.path.exists(new_file):
        raise FileNotFoundError(f"Target file '{new_file}' not found")

    loader = ContractLoader()
    checker = ContractCompatibilityChecker()

    old_contract = loader.load(old_file)
    new_contract = loader.load(new_file)

    try:
        severity_enum = Severity[severity_threshold.upper()]
    except KeyError:
        raise ValueError(f"Invalid severity threshold: {severity_threshold}. Must be one of: HIGH, MEDIUM, LOW, INFO")

    result = checker.check_compatibility(
        old_contract,
        new_contract,
        ignore_non_breaking=ignore_non_breaking,
        severity_threshold=severity_enum
    )

    return result.is_compatible, result.reasons, {
        'is_compatible': result.is_compatible,
        'incompatible_count': result.incompatibility_count,
        'routes': result.incompatible_routes,
        'fields': result.incompatible_fields,
        'responses': result.incompatible_responses,
        'details': result.compatibility_details
    }
