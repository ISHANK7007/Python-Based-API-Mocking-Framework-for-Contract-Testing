from dataclasses import dataclass, field
from typing import Dict, List, Any
import json
import jsonpatch
from contract.contract_entry import ContractEntry, Route, Response


@dataclass
class DiffResult:
    """Base class for diff results."""
    is_different: bool = False


@dataclass
class RouteDiff(DiffResult):
    """Represents differences between routes in two contract versions."""
    added_routes: List[Dict[str, Any]] = field(default_factory=list)
    removed_routes: List[Dict[str, Any]] = field(default_factory=list)
    modified_routes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchemaDiff(DiffResult):
    """Represents differences between JSON schemas."""
    added_properties: Dict[str, Any] = field(default_factory=dict)
    removed_properties: Dict[str, Any] = field(default_factory=dict)
    modified_properties: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    required_changes: Dict[str, Any] = field(default_factory=dict)
    type_changes: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ResponseDiff(DiffResult):
    """Represents differences between response definitions."""
    added_status_codes: List[str] = field(default_factory=list)
    removed_status_codes: List[str] = field(default_factory=list)
    modified_responses: Dict[str, Any] = field(default_factory=dict)
    field_diffs: Dict[str, SchemaDiff] = field(default_factory=dict)
