import pytest
from contract.contract_version import ContractVersion  # Adjust if located elsewhere


def pytest_configure(config):
    """Register custom markers for contract-based testing."""
    config.addinivalue_line(
        "markers",
        "contract(version): specify the contract version to use for the test"
    )
    config.addinivalue_line(
        "markers",
        "contract_versions(versions): run test against multiple contract versions"
    )


@pytest.fixture
def contract_version(request, contracts_dir) -> ContractVersion:
    """
    Resolve the contract version for the test.

    Priority:
    1. @pytest.mark.contract on test function
    2. @pytest.mark.parametrize via @contract_versions(...)
    3. @pytest.mark.contract on class
    4. --default-contract-version (CLI fallback)
    """

    # 1. Test-level marker
    marker = request.node.get_closest_marker("contract")
    if marker and marker.args:
        version_str = marker.args[0]
        return ContractVersion.parse(version_str, contracts_dir)

    # 2. Parametrized via @contract_versions(...)
    if hasattr(request, "param") and isinstance(request.param, str):
        return ContractVersion.parse(request.param, contracts_dir)

    # 3. Class-level marker (check safely)
    test_cls = getattr(request.node, "cls", None)
    if test_cls:
        for cls_marker in getattr(test_cls, "pytestmark", []):
            if cls_marker.name == "contract" and cls_marker.args:
                version_str = cls_marker.args[0]
                return ContractVersion.parse(version_str, contracts_dir)

    # 4. Default version from CLI/config
    default_version = request.config.getoption("--default-contract-version", default=None)
    if default_version:
        return ContractVersion.parse(default_version, contracts_dir)

    pytest.fail("No contract version specified for this test. Use @pytest.mark.contract or pass --default-contract-version.")
