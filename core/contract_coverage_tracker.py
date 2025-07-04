import pytest
from contract.contract_version import contract_versions, contract_major_versions

@contract_versions("users-v1.0.0", "users-v1.1.0", "users-v2.0.0")
def test_get_users(contract_version, validated_api_client):
    """Test runs three times, once for each contract version."""
    response = validated_api_client.get("/users")
    assert response.status_code == 200, f"Unexpected status code: {response.status_code}"

    json_data = response.json()

    if contract_version.version.startswith("1."):
        # v1.x behavior
        assert "items" in json_data, "Expected 'items' key in v1.x response"
    elif contract_version.version.startswith("2."):
        # v2.x behavior
        assert "data" in json_data, "Expected 'data' key in v2.x response"
    else:
        pytest.fail(f"Unsupported contract version: {contract_version.version}")


@contract_major_versions("users", 1, 2, 3)
def test_across_major_versions(contract_version, validated_api_client):
    """Test runs with the latest minor version of each specified major version."""
    response = validated_api_client.get("/users")
    assert response.status_code == 200, f"Unexpected status code for {contract_version.version}"

    json_data = response.json()

    if contract_version.version.startswith("1."):
        assert "items" in json_data, "Expected 'items' in v1.x"
    elif contract_version.version.startswith("2."):
        assert "data" in json_data, "Expected 'data' in v2.x"
    elif contract_version.version.startswith("3."):
        assert "users" in json_data or "records" in json_data, "Expected 'users' or 'records' in v3.x"
    else:
        pytest.fail(f"Unhandled major version: {contract_version.version}")
