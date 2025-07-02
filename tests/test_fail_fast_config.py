import pytest
import yaml

def test_contract_snapshot_compatibility(contract_version, snapshot_verifier):
    """Verify that the contract hasn't changed in incompatible ways."""
    # Load contract YAML from resolved contract path
    try:
        with open(contract_version.contract_path, 'r') as f:
            contract_data = yaml.safe_load(f)
    except FileNotFoundError:
        pytest.fail(f"Contract file not found at path: {contract_version.contract_path}")
    except yaml.YAMLError as e:
        pytest.fail(f"Failed to parse contract YAML: {e}")

    # Compare with expected snapshot
    result = snapshot_verifier.compare_with_snapshot(
        snapshot_name=f"contract.{contract_version.version}",
        data=contract_data
    )

    if result.get("status") == "failed":
        mismatches = result.get("mismatches", "Unknown mismatch")
        pytest.fail(
            f"Contract {contract_version.version} has changed incompatibly:\n{mismatches}"
        )
