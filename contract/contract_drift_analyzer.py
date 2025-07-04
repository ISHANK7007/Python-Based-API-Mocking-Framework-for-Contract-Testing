import json
from typing import Dict, List, Any, Set, Tuple

class ContractDriftAnalyzer:
    """
    A class that analyzes differences between two API contract files.
    """
    
    def __init__(self, old_contract_path: str, new_contract_path: str):
        """
        Initialize with paths to old and new contract files.
        
        Args:
            old_contract_path: Path to the original contract file
            new_contract_path: Path to the new contract file
        """
        self.old_contract_path = old_contract_path
        self.new_contract_path = new_contract_path
        self.old_contract = None
        self.new_contract = None
        
    def load_contracts(self) -> None:
        """Load the contract files into memory."""
        try:
            with open(self.old_contract_path, 'r') as f:
                self.old_contract = json.load(f)
            with open(self.new_contract_path, 'r') as f:
                self.new_contract = json.load(f)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in contract files")
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Contract file not found: {e.filename}")
    
    def analyze_drift(self) -> Dict[str, Any]:
        """
        Analyze differences between the two contracts.
        
        Returns:
            A dictionary containing structured differences
        """
        if not self.old_contract or not self.new_contract:
            self.load_contracts()
            
        diff = {
            "added_routes": [],
            "removed_routes": [],
            "modified_routes": [],
            "summary": {}
        }
        
        # Get route keys from both contracts
        old_routes = self._extract_routes(self.old_contract)
        new_routes = self._extract_routes(self.new_contract)
        
        # Find added routes
        added_route_keys = new_routes.keys() - old_routes.keys()
        for route_key in added_route_keys:
            route_info = new_routes[route_key]
            diff["added_routes"].append({
                "path": route_info["path"],
                "method": route_info["method"],
                "details": route_info["details"]
            })
        
        # Find removed routes
        removed_route_keys = old_routes.keys() - new_routes.keys()
        for route_key in removed_route_keys:
            route_info = old_routes[route_key]
            diff["removed_routes"].append({
                "path": route_info["path"],
                "method": route_info["method"],
                "details": route_info["details"]
            })
        
        # Find modified routes
        common_route_keys = old_routes.keys() & new_routes.keys()
        for route_key in common_route_keys:
            old_route = old_routes[route_key]
            new_route = new_routes[route_key]
            
            changes = self._compare_route_details(old_route["details"], new_route["details"])
            if changes["has_changes"]:
                diff["modified_routes"].append({
                    "path": old_route["path"],
                    "method": old_route["method"],
                    "changes": changes
                })
        
        # Create summary
        diff["summary"] = {
            "added_routes_count": len(diff["added_routes"]),
            "removed_routes_count": len(diff["removed_routes"]),
            "modified_routes_count": len(diff["modified_routes"]),
            "unchanged_routes_count": len(common_route_keys) - len(diff["modified_routes"]),
            "total_drift_score": len(diff["added_routes"]) + len(diff["removed_routes"]) + len(diff["modified_routes"])
        }
        
        return diff
    
    def _extract_routes(self, contract: Dict) -> Dict[str, Dict]:
        """
        Extract routes from a contract into a dictionary.
        
        Args:
            contract: The contract dictionary
            
        Returns:
            A dictionary mapping route keys (path+method) to route details
        """
        routes = {}
        
        # This is a simplistic implementation - adjust based on actual contract format
        for path, path_info in contract.get("paths", {}).items():
            for method, details in path_info.items():
                route_key = f"{path}:{method}"
                routes[route_key] = {
                    "path": path,
                    "method": method,
                    "details": details
                }
        
        return routes
    
    def _compare_route_details(self, old_details: Dict, new_details: Dict) -> Dict[str, Any]:
        """
        Compare details of a specific route between old and new contracts.
        
        Args:
            old_details: Details from the old contract
            new_details: Details from the new contract
            
        Returns:
            A dictionary of differences
        """
        changes = {
            "has_changes": False,
            "request_schema_changes": self._compare_schemas(
                old_details.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {}),
                new_details.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
            ),
            "response_changes": {},
            "parameter_changes": self._compare_parameters(
                old_details.get("parameters", []),
                new_details.get("parameters", [])
            )
        }
        
        # Compare responses
        old_responses = old_details.get("responses", {})
        new_responses = new_details.get("responses", {})
        
        # Get all status codes from both
        status_codes = set(old_responses.keys()) | set(new_responses.keys())
        
        response_changes = {}
        for status in status_codes:
            old_response = old_responses.get(status, {})
            new_response = new_responses.get(status, {})
            
            if status not in old_responses:
                response_changes[status] = {"type": "added", "details": new_response}
                changes["has_changes"] = True
            elif status not in new_responses:
                response_changes[status] = {"type": "removed", "details": old_response}
                changes["has_changes"] = True
            else:
                # Compare response schemas
                old_schema = old_response.get("content", {}).get("application/json", {}).get("schema", {})
                new_schema = new_response.get("content", {}).get("application/json", {}).get("schema", {})
                
                schema_diff = self._compare_schemas(old_schema, new_schema)
                if schema_diff["has_changes"]:
                    response_changes[status] = {"type": "modified", "schema_changes": schema_diff}
                    changes["has_changes"] = True
        
        changes["response_changes"] = response_changes
        
        # If any section has changes, mark the whole route as changed
        if (changes["request_schema_changes"]["has_changes"] or 
            changes["parameter_changes"]["has_changes"] or
            response_changes):
            changes["has_changes"] = True
            
        return changes
    
    def _compare_schemas(self, old_schema: Dict, new_schema: Dict) -> Dict[str, Any]:
        """
        Compare two JSON schemas and identify differences.
        
        Args:
            old_schema: The original schema
            new_schema: The new schema
            
        Returns:
            A dictionary describing differences between schemas
        """
        changes = {
            "has_changes": False,
            "added_properties": [],
            "removed_properties": [],
            "modified_properties": []
        }
        
        # Compare basic schema properties
        if old_schema.get("type") != new_schema.get("type"):
            changes["type_changed"] = {
                "old": old_schema.get("type"),
                "new": new_schema.get("type")
            }
            changes["has_changes"] = True
        
        # Handle different types of schemas
        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})
        
        # Added properties
        added_props = set(new_props.keys()) - set(old_props.keys())
        for prop in added_props:
            changes["added_properties"].append({
                "name": prop,
                "schema": new_props[prop]
            })
            changes["has_changes"] = True
        
        # Removed properties
        removed_props = set(old_props.keys()) - set(new_props.keys())
        for prop in removed_props:
            changes["removed_properties"].append({
                "name": prop,
                "schema": old_props[prop]
            })
            changes["has_changes"] = True
        
        # Modified properties
        common_props = set(old_props.keys()) & set(new_props.keys())
        for prop in common_props:
            if old_props[prop] != new_props[prop]:
                changes["modified_properties"].append({
                    "name": prop,
                    "old_schema": old_props[prop],
                    "new_schema": new_props[prop]
                })
                changes["has_changes"] = True
        
        # Compare required fields
        old_required = set(old_schema.get("required", []))
        new_required = set(new_schema.get("required", []))
        
        if old_required != new_required:
            changes["required_fields_changed"] = {
                "added": list(new_required - old_required),
                "removed": list(old_required - new_required)
            }
            changes["has_changes"] = True
            
        return changes
    
    def _compare_parameters(self, old_params: List[Dict], new_params: List[Dict]) -> Dict[str, Any]:
        """
        Compare API endpoint parameters.
        
        Args:
            old_params: List of parameter objects from old contract
            new_params: List of parameter objects from new contract
            
        Returns:
            A dictionary describing differences in parameters
        """
        changes = {
            "has_changes": False,
            "added_parameters": [],
            "removed_parameters": [],
            "modified_parameters": []
        }
        
        # Create dictionaries for easier comparison
        old_params_dict = {f"{p.get('in')}:{p.get('name')}": p for p in old_params}
        new_params_dict = {f"{p.get('in')}:{p.get('name')}": p for p in new_params}
        
        # Find added parameters
        added_param_keys = new_params_dict.keys() - old_params_dict.keys()
        for key in added_param_keys:
            changes["added_parameters"].append(new_params_dict[key])
            changes["has_changes"] = True
        
        # Find removed parameters
        removed_param_keys = old_params_dict.keys() - new_params_dict.keys()
        for key in removed_param_keys:
            changes["removed_parameters"].append(old_params_dict[key])
            changes["has_changes"] = True
        
        # Find modified parameters
        common_param_keys = old_params_dict.keys() & new_params_dict.keys()
        for key in common_param_keys:
            old_param = old_params_dict[key]
            new_param = new_params_dict[key]
            
            # Compare for differences
            if old_param != new_param:
                changes["modified_parameters"].append({
                    "name": old_param.get("name"),
                    "in": old_param.get("in"),
                    "old": old_param,
                    "new": new_param
                })
                changes["has_changes"] = True
                
        return changes

    def generate_report(self, output_format: str = "json") -> str:
        """
        Generate a formatted report of contract differences.
        
        Args:
            output_format: The format to output (json, text, html)
            
        Returns:
            A formatted report as a string
        """
        diff = self.analyze_drift()
        
        if output_format == "json":
            return json.dumps(diff, indent=2)
        elif output_format == "text":
            # Generate a text report
            report = []
            report.append("# API Contract Drift Analysis")
            report.append(f"\nSummary:")
            report.append(f"- Added routes: {diff['summary']['added_routes_count']}")
            report.append(f"- Removed routes: {diff['summary']['removed_routes_count']}")
            report.append(f"- Modified routes: {diff['summary']['modified_routes_count']}")
            report.append(f"- Unchanged routes: {diff['summary']['unchanged_routes_count']}")
            report.append(f"- Total drift score: {diff['summary']['total_drift_score']}")
            
            if diff["added_routes"]:
                report.append("\n## Added Routes")
                for route in diff["added_routes"]:
                    report.append(f"\n- {route['method'].upper()} {route['path']}")
            
            if diff["removed_routes"]:
                report.append("\n## Removed Routes")
                for route in diff["removed_routes"]:
                    report.append(f"\n- {route['method'].upper()} {route['path']}")
            
            if diff["modified_routes"]:
                report.append("\n## Modified Routes")
                for route in diff["modified_routes"]:
                    report.append(f"\n### {route['method'].upper()} {route['path']}")
                    changes = route["changes"]
                    
                    if changes["request_schema_changes"]["has_changes"]:
                        report.append("\nRequest Schema Changes:")
                        req_changes = changes["request_schema_changes"]
                        
                        if req_changes.get("added_properties"):
                            report.append("  Added properties:")
                            for prop in req_changes["added_properties"]:
                                report.append(f"  - {prop['name']}")
                        
                        if req_changes.get("removed_properties"):
                            report.append("  Removed properties:")
                            for prop in req_changes["removed_properties"]:
                                report.append(f"  - {prop['name']}")
                        
                        if req_changes.get("modified_properties"):
                            report.append("  Modified properties:")
                            for prop in req_changes["modified_properties"]:
                                report.append(f"  - {prop['name']}")
                    
                    if changes["response_changes"]:
                        report.append("\nResponse Changes:")
                        for status, resp_change in changes["response_changes"].items():
                            report.append(f"  Status {status} - {resp_change['type']}")
            
            return "\n".join(report)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")