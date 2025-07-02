import pytest
import yaml
from typing import Dict, Any
from contract.contract_version import ContractVersion  # Adjust if needed


# ----- Contract Injection and Validation Extensions -----

@pytest.fixture
def contract_data(contract_version) -> Dict[str, Any]:
    """Load and parse the contract data for inspection or validation."""
    with open(contract_version.contract_path, 'r') as f:
        return yaml.safe_load(f)


@pytest.fixture
def contract_validator(contract_version, snapshot_verifier):
    """
    Create a validator that checks requests/responses against the contract
    using optional snapshot validation.
    """
    class ContractValidator:
        def __init__(self, contract_version, snapshot_verifier):
            self.contract_version = contract_version
            self.snapshot_verifier = snapshot_verifier
            self.schemas = {}
            self._load_contract()

        def _load_contract(self):
            with open(self.contract_version.contract_path, 'r') as f:
                self.contract = yaml.safe_load(f)

            for path, methods in self.contract.get("paths", {}).items():
                for method, definition in methods.items():
                    endpoint_id = f"{method.upper()} {path}"
                    self.schemas[endpoint_id] = {
                        "request": self._extract_request_schema(definition),
                        "response": self._extract_response_schema(definition)
                    }

        def _extract_request_schema(self, definition):
            request_body = definition.get("requestBody", {}).get("content", {})
            for content_def in request_body.values():
                if "schema" in content_def:
                    return content_def["schema"]
            return None

        def _extract_response_schema(self, definition):
            for code, response_def in definition.get("responses", {}).items():
                if str(code).startswith("2"):
                    content = response_def.get("content", {})
                    for content_def in content.values():
                        if "schema" in content_def:
                            return content_def["schema"]
            return None

        def validate_request(self, method: str, path: str, data: Any, snapshot_name=None):
            endpoint_id = f"{method.upper()} {path}"
            schema = self.schemas.get(endpoint_id, {}).get("request")
            if not schema:
                pytest.fail(f"No request schema for {endpoint_id} in contract {self.contract_version.version}")

            # Simulated snapshot-based validation
            if snapshot_name:
                variant = f"{self.contract_version.version}.request"
                result = self.snapshot_verifier.compare_with_snapshot(snapshot_name, data, variant=variant)
                if result.get("status") == "failed":
                    pytest.fail(f"Request mismatch: {result['mismatches']}")

        def validate_response(self, method: str, path: str, data: Any, snapshot_name=None):
            endpoint_id = f"{method.upper()} {path}"
            schema = self.schemas.get(endpoint_id, {}).get("response")
            if not schema:
                pytest.fail(f"No response schema for {endpoint_id} in contract {self.contract_version.version}")

            # Simulated snapshot-based validation
            if snapshot_name:
                variant = f"{self.contract_version.version}.response"
                result = self.snapshot_verifier.compare_with_snapshot(snapshot_name, data, variant=variant)
                if result.get("status") == "failed":
                    pytest.fail(f"Response mismatch: {result['mismatches']}")

    return ContractValidator(contract_version, snapshot_verifier)


# ----- Integration with HTTP Client -----

@pytest.fixture
def validated_api_client(api_client, contract_validator, request):
    """
    API client that automatically validates requests and responses
    against the active contract using the contract_validator.
    """
    original_request = api_client.request
    base_url = getattr(api_client, "base_url", "")

    def validated_request(method, url, **kwargs):
        # Normalize path from full URL
        path = url.replace(base_url, "", 1).lstrip("/")
        data = kwargs.get("json") or kwargs.get("data")
        test_name = request.node.nodeid.replace("::", ".").replace("/", ".")

        if data:
            contract_validator.validate_request(
                method, path, data, snapshot_name=f"{test_name}.{method}.{path}"
            )

        response = original_request(method, url, **kwargs)

        try:
            response_data = response.json()
            contract_validator.validate_response(
                method, path, response_data, snapshot_name=f"{test_name}.{method}.{path}"
            )
        except ValueError:
            # Response wasn't JSON
            pass

        return response

    # Patch the request method
    api_client.request = validated_request
    return api_client
