def test_version_header_behavior(contract_version, versioned_api_client):
    """Test that API responds appropriately to version headers."""
    response = versioned_api_client.get("/users")
    assert response.status_code == 200
    
    # API should respect versioning headers
    if contract_version.version.startswith("1."):
        assert response.json().get("api_version") == "1.0"
    elif contract_version.version.startswith("2."):
        assert response.json().get("api_version") == "2.0"