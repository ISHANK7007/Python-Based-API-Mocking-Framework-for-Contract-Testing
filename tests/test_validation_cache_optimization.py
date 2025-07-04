import pytest

# Single version test using mark
@pytest.mark.contract("users-v1.0.0")
def test_get_user(contract_version, validated_api_client):
    """Test using v1.0.0 contract"""
    assert contract_version.version == "users-v1.0.0"
    response = validated_api_client.get("/users/1")
    assert response.status_code == 200


# Class-level contract version marker
@pytest.mark.contract("users-v1.0.0")
class TestUserAPI:

    def test_get_user(self, contract_version, validated_api_client):
        """Inherits contract from class-level marker"""
        assert contract_version.version == "users-v1.0.0"
        response = validated_api_client.get("/users/1")
        assert response.status_code == 200

    @pytest.mark.contract("users-v2.0.0")  # Overrides class marker
    def test_get_user_v2(self, contract_version, validated_api_client):
        """Overrides contract to use v2.0.0 for this specific test"""
        assert contract_version.version == "users-v2.0.0"
        response = validated_api_client.get("/users/1")
        assert response.status_code == 200
