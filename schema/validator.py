import json
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from jsonschema import validate, ValidationError as JsonSchemaError, Draft7Validator
from jsonschema.exceptions import best_match

from contract.contract_entry import ContractEntry

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors with structured details."""

    def __init__(self,
                 message: str,
                 error_type: str = "schema_violation",
                 field: Optional[str] = None,
                 details: Any = None):
        self.message = message
        self.error_type = error_type
        self.field = field
        self.details = details
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": self.error_type,
            "message": self.message
        }
        if self.field:
            result["field"] = self.field
        if self.details:
            result["details"] = self.details
        return result

    @classmethod
    def from_jsonschema_error(cls, error: JsonSchemaError) -> 'ValidationError':
        path = ".".join(str(p) for p in error.path) if error.path else None
        message = f"Validation failed for field '{path}': {error.message}" if path else f"Validation failed: {error.message}"
        return cls(
            message=message,
            error_type="schema_violation",
            field=path,
            details={
                "schema_path": list(error.schema_path),
                "validation_error": error.message,
                "instance": error.instance
            }
        )


class SchemaValidator:
    """
    Validates incoming JSON requests against JSON schema definitions.
    """

    @staticmethod
    def validate_request_body(contract: ContractEntry, request_body: Any) -> Tuple[bool, Optional[Dict[str, Any]]]:
        if not contract.request_body_schema:
            return True, None
        if request_body is None:
            return False, ValidationError(
                message="Request body is required but none was provided",
                error_type="missing_body"
            ).to_dict()

        try:
            validate(instance=request_body, schema=contract.request_body_schema)
            return True, None
        except JsonSchemaError as e:
            return False, ValidationError.from_jsonschema_error(e).to_dict()

    @staticmethod
    def validate_request_headers(contract: ContractEntry, headers: Dict[str, str]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        if not contract.request_headers:
            return True, None

        missing = []
        invalid = []

        for name, expected in contract.request_headers.items():
            name_lower = name.lower()
            found = False

            for actual_name, actual_value in headers.items():
                if actual_name.lower() == name_lower:
                    found = True
                    if expected is not None and actual_value != expected:
                        invalid.append({
                            "name": name,
                            "expected": expected,
                            "actual": actual_value
                        })
                    break

            if not found:
                missing.append(name)

        if missing or invalid:
            details = {}
            if missing:
                details["missing_headers"] = missing
            if invalid:
                details["invalid_headers"] = invalid

            return False, ValidationError(
                message="Header validation failed",
                error_type="header_validation",
                details=details
            ).to_dict()

        return True, None

    @staticmethod
    def validate_query_parameters(contract: ContractEntry, query_params: Dict[str, str]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        if not contract.query_parameters:
            return True, None

        missing = []
        for param, definition in contract.query_parameters.items():
            if definition.required and param not in query_params:
                missing.append(param)

        if missing:
            return False, ValidationError(
                message=f"Missing required query parameters: {', '.join(missing)}",
                error_type="missing_query_params",
                details={"missing_params": missing}
            ).to_dict()

        return True, None

    @staticmethod
    def get_validation_errors(
        contract: ContractEntry,
        request_body: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None
    ) -> List[Dict[str, Any]]:
        errors = []
        headers = headers or {}
        query_params = query_params or {}

        is_valid, err = SchemaValidator.validate_request_body(contract, request_body)
        if not is_valid:
            errors.append(err)

        is_valid, err = SchemaValidator.validate_request_headers(contract, headers)
        if not is_valid:
            errors.append(err)

        is_valid, err = SchemaValidator.validate_query_parameters(contract, query_params)
        if not is_valid:
            errors.append(err)

        return errors

    @staticmethod
    def find_all_schema_errors(schema: Dict[str, Any], data: Any) -> List[Dict[str, Any]]:
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(data))
        return [ValidationError.from_jsonschema_error(e).to_dict() for e in errors]

    @staticmethod
    def parse_json_safely(json_str: str) -> Tuple[Any, Optional[Dict[str, Any]]]:
        try:
            return json.loads(json_str), None
        except json.JSONDecodeError as e:
            return None, ValidationError(
                message=f"Invalid JSON: {str(e)}",
                error_type="invalid_json",
                details={"line": e.lineno, "column": e.colno, "position": e.pos}
            ).to_dict()
