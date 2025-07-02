from typing import List, Dict, Any, Set, Tuple, Optional
import yaml
from pydantic import ValidationError
import logging
from pathlib import Path

from contract.contract_entry import ContractEntry, HttpMethod
from contract.contract_loader import ContractLoadError  # Reuse from existing module

logger = logging.getLogger(__name__)

class ContractConflictError(Exception):
    """Exception raised when conflicting route definitions are found."""
    
    def __init__(self, message: str, conflicts: List[Dict[str, Any]], file_path: Optional[str] = None):
        self.message = message
        self.conflicts = conflicts
        self.file_path = file_path
        details = "\n".join([f"- {conflict['method']} {conflict['path']} (lines: {conflict['lines']})" 
                             for conflict in conflicts])
        self.details = f"{message}\n{details}"
        super().__init__(self.details)


class EnhancedContractLoader:
    """Enhanced version of ContractLoader with duplicate detection."""

    @staticmethod
    def _extract_line_numbers(yaml_content: str, routes_data: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        lines = yaml_content.split('\n')
        route_indices: Dict[int, Dict[str, Any]] = {}

        for i, route in enumerate(routes_data):
            method = route.get('method', '')
            path = route.get('path', '')
            if not method or not path:
                continue

            method_line = -1
            path_line = -1
            for j, line in enumerate(lines, 1):
                if f"method: {method}" in line:
                    method_line = j
                if f"path: {path}" in line:
                    path_line = j

            route_indices[i] = {
                'method_line': method_line,
                'path_line': path_line,
                'start_line': min(method_line, path_line) if method_line > 0 and path_line > 0 else max(method_line, path_line)
            }

        return route_indices

    @staticmethod
    def _check_for_duplicates(routes_data: List[Dict[str, Any]], 
                              route_indices: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen_routes: Dict[Tuple[str, str], List[int]] = {}
        conflicts = []

        for i, route in enumerate(routes_data):
            method = route.get('method', '')
            path = route.get('path', '')
            if not method or not path:
                continue

            route_key = (method, path)

            if route_key in seen_routes:
                lines = seen_routes[route_key] + [i]
                line_numbers = [route_indices[idx]['start_line'] for idx in lines if idx in route_indices]

                conflicts.append({
                    'method': method,
                    'path': path,
                    'indices': lines,
                    'lines': line_numbers,
                    'routes': [routes_data[idx] for idx in lines]
                })
            else:
                seen_routes[route_key] = [i]

        return conflicts

    @staticmethod
    def load_from_file(file_path: Path, allow_duplicates: bool = False) -> List[ContractEntry]:
        try:
            with open(file_path, 'r') as f:
                yaml_content = f.read()
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                raise ContractLoadError("Contract data must be a dictionary", str(file_path))

            routes_data = data.get("routes", []) or data.get("entries", [])
            if not isinstance(routes_data, list):
                raise ContractLoadError("Routes must be provided as a list", str(file_path))

            route_indices = EnhancedContractLoader._extract_line_numbers(yaml_content, routes_data)
            conflicts = EnhancedContractLoader._check_for_duplicates(routes_data, route_indices)

            if conflicts and not allow_duplicates:
                raise ContractConflictError(
                    f"Found {len(conflicts)} duplicate route definitions in {file_path}",
                    conflicts,
                    str(file_path)
                )
            elif conflicts:
                logger.warning(f"Found {len(conflicts)} duplicate route definitions in {file_path}:")
                for conflict in conflicts:
                    logger.warning(f"  {conflict['method']} {conflict['path']} (lines: {conflict['lines']})")

            validated_entries = []
            validation_errors = []

            for i, entry_data in enumerate(routes_data):
                try:
                    if "id" not in entry_data and "method" in entry_data and "path" in entry_data:
                        entry_data["id"] = f"{entry_data['method']}_{entry_data['path'].replace('/', '_').replace('{', '').replace('}', '')}"

                    entry = ContractEntry.parse_obj(entry_data)
                    validated_entries.append(entry)
                except ValidationError as e:
                    line_info = ""
                    if i in route_indices:
                        start_line = route_indices[i]['start_line']
                        line_info = f" (near line {start_line})"
                    validation_errors.append(f"Entry #{i+1}{line_info}: {str(e)}")

            if validation_errors:
                error_details = "\n".join(validation_errors)
                raise ContractLoadError(
                    f"Contract validation failed with {len(validation_errors)} errors", 
                    str(file_path), 
                    error_details
                )

            return validated_entries

        except yaml.YAMLError as e:
            raise ContractLoadError("Failed to parse YAML", str(file_path), e)
        except Exception as e:
            if isinstance(e, (ContractLoadError, ContractConflictError)):
                raise
            raise ContractLoadError(f"Unexpected error: {str(e)}", str(file_path), e)

    @staticmethod
    def validate_no_conflicts(contracts: List[ContractEntry]) -> List[Dict[str, Any]]:
        seen_routes: Dict[Tuple[HttpMethod, str], List[ContractEntry]] = {}
        conflicts = []

        for contract in contracts:
            route_key = (contract.method, contract.path)
            if route_key in seen_routes:
                conflicting_contracts = seen_routes[route_key] + [contract]
                conflicts.append({
                    'method': contract.method.value,
                    'path': contract.path,
                    'contracts': conflicting_contracts,
                    'ids': [c.id for c in conflicting_contracts if c.id]
                })
            else:
                seen_routes[route_key] = [contract]

        return conflicts
