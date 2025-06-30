from typing import List, Dict, Any


def classify_breaking_changes(diff_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Analyze a diff_result and return a list of breaking changes.

    Each breaking change is a dictionary describing the type of break, location, and metadata.
    """
    breaking_changes = []

    # 1. Removed Routes
    for route in diff_result.get("routes", {}).get("removed_routes", []):
        breaking_changes.append({
            "type": "ROUTE_REMOVED",
            "path": route["path"],
            "method": route["method"],
            "severity": "HIGH"
        })

    # 2. Removed Required Request Fields
    for path, details in diff_result.get("detailed_diffs", {}).items():
        request_schema = details.get("request_schema", {})
        required_changes = request_schema.get("required_changes", {})
        for field in required_changes.get("no_longer_required", []):
            breaking_changes.append({
                "type": "REQUIRED_FIELD_REMOVED",
                "path": path,
                "field": field,
                "severity": "HIGH"
            })

    # 3. Type Changed in Request Fields
    for path, details in diff_result.get("detailed_diffs", {}).items():
        request_schema = details.get("request_schema", {})
        modified = request_schema.get("modified_properties", {})
        for field, changes in modified.items():
            if "type" in changes.get("changes", {}):
                breaking_changes.append({
                    "type": "FIELD_TYPE_CHANGED",
                    "path": path,
                    "field": field,
                    "from": changes["changes"]["type"]["from"],
                    "to": changes["changes"]["type"]["to"],
                    "severity": "MEDIUM"
                })

    # 4. Removed Response Status Codes
    for path, details in diff_result.get("detailed_diffs", {}).items():
        responses = details.get("responses", {})
        for status in responses.get("removed_status_codes", []):
            breaking_changes.append({
                "type": "RESPONSE_STATUS_REMOVED",
                "path": path,
                "status_code": status,
                "severity": "HIGH"
            })

    # 5. Removed Response Fields
    for path, details in diff_result.get("detailed_diffs", {}).items():
        responses = details.get("responses", {})
        for status, schema in responses.get("field_diffs", {}).items():
            for field in schema.removed_properties:
                breaking_changes.append({
                    "type": "RESPONSE_FIELD_REMOVED",
                    "path": path,
                    "status_code": status,
                    "field": field,
                    "severity": "HIGH"
                })

    return breaking_changes
