from contract.contract_entry import ContractEntry, HttpMethod, PathParameter, ResponseStub
from schema.validator import SchemaValidator


def example_usage():
    # Create a sample contract with schema, headers, and query params
    contract = ContractEntry(
        method=HttpMethod.POST,
        path="/users",
        request_body_schema={
            "type": "object",
            "required": ["name", "email"],
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string", "format": "email"},
                "age": {"type": "integer", "minimum": 18}
            },
            "additionalProperties": False
        },
        request_headers={"Content-Type": "application/json", "Authorization": None},
        query_parameters={"version": PathParameter(name="version", required=True)},
        response_stub=ResponseStub(status_code=201, body={"id": "123"})
    )

    print("\n✅ Valid request:")
    valid_body = {
        "name": "John Doe",
        "email": "john@example.com",
        "age": 25
    }
    valid_headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer token123"
    }
    valid_query = {
        "version": "1.0"
    }

    valid_errors = SchemaValidator.get_validation_errors(
        contract,
        request_body=valid_body,
        headers=valid_headers,
        query_params=valid_query
    )
    print("Validation errors (should be empty):", valid_errors)

    print("\n❌ Invalid request:")
    invalid_body = {
        "name": "John Doe",
        # "email" is missing
        "age": "not-a-number"
    }
    invalid_headers = {
        "Content-Type": "text/plain"
        # Missing Authorization
    }
    invalid_query = {}  # Missing "version"

    invalid_errors = SchemaValidator.get_validation_errors(
        contract,
        request_body=invalid_body,
        headers=invalid_headers,
        query_params=invalid_query
    )
    print("Validation errors:")
    for error in invalid_errors:
        print("-", error)

    print("\n📦 JSON parse + validate flow:")
    json_str = '{"name": "John", "email": "john@example.com"}'
    parsed_body, parse_error = SchemaValidator.parse_json_safely(json_str)

    if parse_error:
        print("JSON parsing error:", parse_error['message'])
    else:
        is_valid, validation_error = SchemaValidator.validate_request_body(contract, parsed_body)
        if not is_valid:
            print("Validation error:", validation_error["message"])
            print("Details:", validation_error.get("details"))


# Optional: run example when file is executed directly
if __name__ == "__main__":
    example_usage()
