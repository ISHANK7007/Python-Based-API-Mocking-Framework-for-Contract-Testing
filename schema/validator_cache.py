def pytest_addoption(parser):
    group = parser.getgroup("contract-testing")
    group.addoption(
        "--contracts-dir",
        default=None,
        help="Directory containing contract definition files"
    )
    group.addoption(
        "--default-contract-version",
        default=None,
        help="Default contract version to use when not specified by test"
    )
    group.addoption(
        "--contract-tag",
        default=None,
        help="Tag to select contract versions (e.g., 'stable', 'latest', 'dev')"
    )

# Add support for contract tags in configuration file
def get_contract_by_tag(contracts_dir, name, tag):
    """Get contract version by tag from pyproject.toml or similar config."""
    # Read from config file (e.g., pyproject.toml, pytest.ini)
    # For simplicity, we're hardcoding some examples
    tags = {
        "latest": {
            "users": "users-v2.0.0",
            "orders": "orders-v3.1.0"
        },
        "stable": {
            "users": "users-v1.2.3",
            "orders": "orders-v2.5.0" 
        },
        "dev": {
            "users": "users-v3.0.0-alpha",
            "orders": "orders-v4.0.0-beta"
        }
    }
    
    if tag not in tags or name not in tags[tag]:
        return None
        
    return tags[tag][name]