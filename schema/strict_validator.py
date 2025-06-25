import json
from typing import Dict, List, Any, Optional, Tuple, Union, Set
from jsonschema import validate, ValidationError as JsonSchemaError
from jsonschema.exceptions import best_match

from contract.contract_entry import ContractEntry  # Fixed import

class ValidationError(Exception):
    """Custom exception for validation errors with structured details."""

    def __init__(
        self,
        message: str,
        error_type: str = "schema_violation",
        field: Optional[str] = None,
        details: Any = None,
        status_code: int = 400
    ):
        self.message = message
        self.error_type = error_type
        self.field = field
        self.details = details
        self.status_code = status_code
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

    def to_response(self) -> Dict[str, Any]:
        return {
            "error": self.to_dict(),
            "status_code": self.status_code
        }

    @classmethod
    def from_jsonschema_error(cls, error: JsonSchemaError) -> 'ValidationError':
        path = ".".join(str(p) for p in error.path) if error.path else None
        error_type = "schema_violation"
        if error.schema_path:
            last_path = error.schema_path[-1] if error.schema_path else None
            if last_path in (
                "type", "format", "required", "enum", "pattern",
                "minLength", "maxLength", "minimum", "maximum"
            ):
                error_type = f"{last_path}_violation"
            elif last_path == "additionalProperties" and not error.schema.get("additionalProperties", True):
                error_type = "extra_field"

        message = f"Validation failed for field '{path}': {error.message}" if path else f"Validation failed: {error.message}"

        return cls(
            message=message,
            error_type=error_type,
            field=path,
            details={
                "schema_path": list(error.schema_path),
                "validation_error": error.message,
                "instance": error.instance
            }
        )

class StrictSchemaValidator:
    @staticmethod
    def _enforce_no_additional_properties(schema: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(schema, dict):
            return schema

        schema_copy = dict(schema)

        if schema_copy.get("type") == "object" and "additionalProperties" not in schema_copy:
            schema_copy["additionalProperties"] = False

        if "properties" in schema_copy and isinstance(schema_copy["properties"], dict):
            properties = schema_copy["properties"]
            for prop_name, prop_schema in properties.items():
                properties[prop_name] = StrictSchemaValidator._enforce_no_additional_properties(prop_schema)

        if "items" in schema_copy and isinstance(schema_copy["items"], dict):
            schema_copy["items"] = StrictSchemaValidator._enforce_no_additional_properties(schema_copy["items"])

        for key in ("oneOf", "anyOf", "allOf"):
            if key in schema_copy and isinstance(schema_copy[key], list):
                schema_copy[key] = [
                    StrictSchemaValidator._enforce_no_additional_properties(s)
                    for s in schema_copy[key]
                ]

        return schema_copy

    @staticmethod
    def validate_request_body(contract: ContractEntry, request_body: Any, strict: bool = True) -> Tuple[bool, Optional[ValidationError]]:
        if not contract.request_body_schema:
            return True, None

        if contract.request_body_schema and request_body is None:
            return False, ValidationError(
                message="Request body is required but none was provided",
                error_type="missing_body"
            )

        try:
            schema = contract.request_body_schema
            if strict:
                schema = StrictSchemaValidator._enforce_no_additional_properties(schema)
            validate(instance=request_body, schema=schema)
            return True, None
        except JsonSchemaError as e:
            return False, ValidationError.from_jsonschema_error(e)

    @staticmethod
    def find_extra_fields(schema: Dict[str, Any], data: Any, path: str = "") -> List[str]:
        extra_fields = []
        if not isinstance(data, dict) or schema.get("type") != "object":
            return extra_fields

        properties = schema.get("properties", {})
        property_names = set(properties.keys())

        pattern_props = schema.get("patternProperties", {})
        if pattern_props:
            import re
            for pattern in pattern_props:
                for key in data.keys():
                    if re.match(pattern, key):
                        property_names.add(key)

        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key
            if key not in property_names:
                extra_fields.append(current_path)
            elif key in properties and isinstance(value, dict) and isinstance(properties[key], dict):
                extra_fields.extend(
                    StrictSchemaValidator.find_extra_fields(properties[key], value, current_path)
                )
            elif (key in properties and isinstance(value, list) and
                  isinstance(properties[key], dict) and "items" in properties[key]):
                items_schema = properties[key].get("items", {})
                for i, item in enumerate(value):
                    item_path = f"{current_path}[{i}]"
                    if isinstance(item, dict):
                        extra_fields.extend(
                            StrictSchemaValidator.find_extra_fields(items_schema, item, item_path)
                        )

        return extra_fields

    @staticmethod
    def generate_extra_fields_error(schema: Dict[str, Any], data: Any) -> Optional[ValidationError]:
        extra_fields = StrictSchemaValidator.find_extra_fields(schema, data)
        if extra_fields:
            return ValidationError(
                message=f"Request contains {len(extra_fields)} field(s) not defined in the schema",
                error_type="extra_fields",
                details={
                    "extra_fields": extra_fields,
                    "allowed_fields": list(schema.get("properties", {}).keys())
                }
            )
        return None

    @staticmethod
    def validate_request(contract: ContractEntry,
                         request_body: Optional[Any] = None,
                         headers: Optional[Dict[str, str]] = None,
                         query_params: Optional[Dict[str, str]] = None,
                         strict: bool = True) -> Tuple[bool, Optional[Dict[str, Any]]]:
        headers = headers or {}
        query_params = query_params or {}
        errors = []

        if contract.request_body_schema:
            is_valid, body_error = StrictSchemaValidator.validate_request_body(contract, request_body, strict)
            if not is_valid:
                errors.append(body_error)
                if body_error.error_type != "extra_field" and request_body is not None:
                    extra_fields_error = StrictSchemaValidator.generate_extra_fields_error(
                        contract.request_body_schema, request_body
                    )
                    if extra_fields_error:
                        errors.append(extra_fields_error)

        # Placeholder: Add header/query validation as needed

        if errors:
            error_response = {
                "status_code": 400,
                "error": {
                    "message": "Request validation failed",
                    "errors": [error.to_dict() for error in errors]
                }
            }
            return False, error_response

        return True, None
