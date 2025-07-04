import os
import sys
from datetime import datetime
from typing import Optional

# Ensure root path is available for module imports
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# --- Safe imports ---
try:
    from contract.contract_version_manager import ContractVersionManager
    from contract.contract_differ import ContractDiffer
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def generate_version_diff_report(contract_name: str, version1: str, version2: str) -> str:
    """
    Generate a human-readable diff report between two contract versions.

    Args:
        contract_name: The name of the contract.
        version1: The older version string (e.g., "1.0.0").
        version2: The newer version string (e.g., "1.1.0").

    Returns:
        A formatted string containing the diff report.
    """
    manager = ContractVersionManager()
    contract_root = os.path.join(ROOT_DIR, "contracts")
    manager.discover_contracts(contract_root)

    v1 = manager.get_version(contract_name, version1)
    v2 = manager.get_version(contract_name, version2)

    if not v1 or not v2:
        return f"Error: One or both versions not found: {version1}, {version2}"

    contract1 = manager.load_contract(v1)
    contract2 = manager.load_contract(v2)

    differ = ContractDiffer()
    diff_result = differ.diff_contracts(contract1, contract2)

    report = []
    report.append(f"# Diff Report: {contract_name} v{version1} → v{version2}")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # --- ROUTES ---
    route_diff = diff_result.get("routes", {})
    report.append("## Routes\n")

    if route_diff.get("added_routes"):
        report.append("### Added Routes")
        for route in route_diff["added_routes"]:
            report.append(f"- {route['method']} {route['path']}")
            if route.get("description"):
                report.append(f"  Description: {route['description']}")
        report.append("")

    if route_diff.get("removed_routes"):
        report.append("### Removed Routes")
        for route in route_diff["removed_routes"]:
            report.append(f"- {route['method']} {route['path']}")
        report.append("")

    if route_diff.get("modified_routes"):
        report.append("### Modified Routes")
        for path, changes in route_diff["modified_routes"].items():
            report.append(f"- {path}")
            if "description" in changes:
                report.append("  Description changed:")
                report.append(f"  - From: {changes['description']['from']}")
                report.append(f"  - To: {changes['description']['to']}")
        report.append("")

    # --- DETAILED SCHEMA DIFFS ---
    detailed_diffs = diff_result.get("detailed_diffs", {})
    if detailed_diffs:
        report.append("## Detailed Changes\n")
        for path, details in detailed_diffs.items():
            report.append(f"### {path}\n")

            schema_diff = details.get("request_schema")
            if schema_diff:
                report.append("#### Request Schema Changes\n")
                if schema_diff.get("added_properties"):
                    report.append("Added Properties:")
                    for prop, def_ in schema_diff["added_properties"].items():
                        report.append(f"- `{prop}` ({def_.get('type', 'unknown')})")
                        if "description" in def_:
                            report.append(f"  Description: {def_['description']}")
                    report.append("")
                if schema_diff.get("removed_properties"):
                    report.append("Removed Properties:")
                    for prop in schema_diff["removed_properties"].keys():
                        report.append(f"- `{prop}`")
                    report.append("")
                if schema_diff.get("modified_properties"):
                    report.append("Modified Properties:")
                    for prop, changes in schema_diff["modified_properties"].items():
                        report.append(f"- `{prop}`")
                        for change_type, change in changes["changes"].items():
                            if isinstance(change, dict):
                                report.append(f"  - {change_type}: `{change['from']}` → `{change['to']}`")
                    report.append("")
                if schema_diff.get("required_changes"):
                    req = schema_diff["required_changes"]
                    if req.get("newly_required"):
                        report.append("  Newly Required:")
                        for field in req["newly_required"]:
                            report.append(f"  - `{field}`")
                    if req.get("no_longer_required"):
                        report.append("  No Longer Required:")
                        for field in req["no_longer_required"]:
                            report.append(f"  - `{field}`")
                    report.append("")

            response_diff = details.get("responses")
            if response_diff:
                report.append("#### Response Changes\n")
                if response_diff.get("added_status_codes"):
                    report.append("Added Status Codes:")
                    for code in response_diff["added_status_codes"]:
                        report.append(f"- `{code}`")
                    report.append("")
                if response_diff.get("removed_status_codes"):
                    report.append("Removed Status Codes:")
                    for code in response_diff["removed_status_codes"]:
                        report.append(f"- `{code}`")
                    report.append("")
                if response_diff.get("modified_responses"):
                    report.append("Modified Responses:")
                    for status, changes in response_diff["modified_responses"].items():
                        report.append(f"- Status Code: `{status}`")
                        if "content_type" in changes:
                            report.append(f"  - Content-Type: `{changes['content_type']['from']}` → `{changes['content_type']['to']}`")
                        if "headers" in changes:
                            if changes["headers"].get("added"):
                                report.append(f"  - Added Headers: {', '.join(changes['headers']['added'])}")
                            if changes["headers"].get("removed"):
                                report.append(f"  - Removed Headers: {', '.join(changes['headers']['removed'])}")
                        if "body" in changes and changes["body"].get("summary"):
                            summary = changes["body"]["summary"]
                            if summary.get("added"):
                                report.append(f"    - Added fields: {len(summary['added'])}")
                            if summary.get("removed"):
                                report.append(f"    - Removed fields: {len(summary['removed'])}")
                            if summary.get("changed"):
                                report.append(f"    - Changed fields: {len(summary['changed'])}")
                    report.append("")

                for status, field_diff in response_diff.get("field_diffs", {}).items():
                    report.append(f"#### Response Body Schema Changes for Status {status}")
                    if field_diff.added_properties:
                        report.append("Added Fields:")
                        for f in field_diff.added_properties:
                            report.append(f"- `{f}`")
                        report.append("")
                    if field_diff.removed_properties:
                        report.append("Removed Fields:")
                        for f in field_diff.removed_properties:
                            report.append(f"- `{f}`")
                        report.append("")
                    if field_diff.modified_properties:
                        report.append("Changed Fields:")
                        for f, changes in field_diff.modified_properties.items():
                            report.append(f"- `{f}`")
                            if "type" in changes["changes"]:
                                report.append(f"  - Type: {changes['changes']['type']['from']} → {changes['changes']['type']['to']}")
                        report.append("")

    return "\n".join(report)


# CLI usage example
if __name__ == "__main__":
    contract = "mock"
    v1 = "1.0.0"
    v2 = "1.1.0"
    print(generate_version_diff_report(contract, v1, v2))
