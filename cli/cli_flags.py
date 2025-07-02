from typing import Dict, Any
from contract.contract_loader import ContractLoader
from contract.contract_diff_formatter import EnhancedDiffFormatter
from core.diff_runner import EnhancedContractDiffer
from core.diff_severity_grouping import SeverityGroupedFormatter

def generate_compatibility_report(from_file: str, to_file: str, 
                                  show_details: bool = False) -> Dict[str, Any]:
    """
    Generate a structured compatibility report between two contract files.

    Args:
        from_file: Path to the source contract file
        to_file: Path to the target contract file
        show_details: Include detailed information about changes

    Returns:
        Dict containing the compatibility report information
    """
    # Load contracts
    loader = ContractLoader()
    differ = EnhancedContractDiffer()

    contract1 = loader.load(from_file)
    contract2 = loader.load(to_file)

    # Generate diff
    diff_result = differ.diff_contracts(contract1, contract2)

    # Extract summaries
    formatter = EnhancedDiffFormatter()
    summaries = formatter.generate_change_summaries(diff_result)

    # Group by severity
    changes_by_severity = SeverityGroupedFormatter.format_changes_by_severity(summaries)

    # Build the report
    report = {
        "source_file": from_file,
        "target_file": to_file,
        "summary": {
            "total_changes": len(summaries),
            "changes_by_severity": {
                str(severity): len(changes) for severity, changes in changes_by_severity.items()
            },
            "breaking_changes": len([s for s in summaries if s.is_breaking]),
            "non_breaking_changes": len([s for s in summaries if not s.is_breaking])
        },
        "changes_by_severity": {}
    }

    # Add changes grouped by severity
    for severity, changes in changes_by_severity.items():
        change_list = []
        for change in changes:
            change_info = {
                "summary": change.get_summary_text(),
                "path": change.path,
                "method": change.method,
                "type": change.change_type.name if change.change_type else "UNKNOWN",
                "is_breaking": change.is_breaking
            }

            if show_details:
                change_info["details"] = change.details

            change_list.append(change_info)

        report["changes_by_severity"][str(severity)] = change_list

    return report
