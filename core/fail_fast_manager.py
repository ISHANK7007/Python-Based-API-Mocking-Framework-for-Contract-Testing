import pytest

@pytest.fixture
def versioned_api_client(api_client, contract_version):
    """Client that sends appropriate API version headers based on contract version."""

    # Safely extract major.minor from version string (e.g., '1.2.3' → '1.2')
    version_parts = contract_version.version.split('.')
    if len(version_parts) < 2:
        raise ValueError(f"Invalid contract version format: '{contract_version.version}'")

    api_version = ".".join(version_parts[:2])

    # Clone the client to avoid mutating global headers
    client = api_client.copy()
    client.headers.update({
        "Accept-Version": api_version,
        "X-API-Version": api_version
    })

    return client
