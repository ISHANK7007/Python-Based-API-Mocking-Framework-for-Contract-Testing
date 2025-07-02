import pytest
from contract.contract_version import contract_versions  # Make sure this exists
from contract.contract_version import contract_version as contract_marker  # Optional alias if needed

@pytest.mark.contract("users-v1.0.0")  # Fixed: corrected marker name
def test_create_user(contract_version, validated_api_client):
    """Test creating a user with v1.0.0 contract."""
    response = validated_api_client.post("/users", json={
        "username": "testuser",
        "email": "test@example.com"
    })

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["username"] == "testuser"


@contract_versions("users-v1.0.0", "users-v1.1.0")  # Fixed: correct decorator
def test_user_api_across_versions(contract_version, validated_api_client):
    """Test user API against multiple contract versions."""
    response = validated_api_client.get("/users")
    assert response.status_code == 200

    data = response.json()
    if contract_version.version.startswith("1.0"):
        # v1.0.0 behavior
        assert "items" in data
    elif contract_version.version.startswith("1.1"):
        # v1.1.0 behavior – e.g., pagination was introduced
        assert "items" in data
        assert "pagination" in data
    else:
        pytest.fail(f"Unhandled contract version: {contract_version.version}")
