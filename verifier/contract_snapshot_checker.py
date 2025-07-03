import os
import pytest
from pathlib import Path
from typing import Dict, Any

from verifier.enhanced_snapshot_verifier import SnapshotVerifier  # ✅ adjust if needed


def pytest_addoption(parser):
    group = parser.getgroup("contract-validation")
    group.addoption(
        "--update-snapshots",
        action="store_true",
        default=False,
        help="Update contract snapshots when mismatches are found"
    )
    group.addoption(
        "--snapshot-dir",
        default="snapshots",
        help="Directory to store contract snapshots"
    )


@pytest.fixture
def contract_options(request):
    return {
        "update_snapshots": request.config.getoption("--update-snapshots"),
        "snapshot_dir": request.config.getoption("--snapshot-dir")
    }


class ContractValidationReport:
    """Store contract validation results for test summary."""

    def __init__(self):
        self.validation_results = []

    def add_result(self, test_id: str, validation_type: str, result: Dict[str, Any]):
        self.validation_results.append({
            "test_id": test_id,
            "type": validation_type,  # "request", "response"
            "result": result
        })

    def generate_report(self) -> str:
        """Generate a human-readable report of validation results."""
        if not self.validation_results:
            return "No contract validation performed."

        report = ["\nContract Validation Summary:"]
        failed_count = sum(1 for r in self.validation_results if r["result"]["status"] == "failed")
        created_count = sum(1 for r in self.validation_results if r["result"]["status"] == "created")
        updated_count = sum(1 for r in self.validation_results if r["result"]["status"] == "updated")

        report.append(f"  - Failed : {failed_count}")
        report.append(f"  - Created: {created_count}")
        report.append(f"  - Updated: {updated_count}")
        report.append(f"  - Total  : {len(self.validation_results)}")

        if failed_count > 0:
            report.append("\nFailed Validations:")
            for r in self.validation_results:
                if r["result"]["status"] == "failed":
                    report.append(f"  - {r['test_id']} ({r['type']}):")
                    mismatches = r["result"].get("mismatches", {})
                    if isinstance(mismatches, dict):
                        for path, msg in mismatches.items():
                            report.append(f"      - {path}: {msg}")
                    else:
                        report.append(f"      - {mismatches}")

        return "\n".join(report)


@pytest.fixture(scope="session")
def contract_validation_report():
    """Provide a report collector that persists across tests."""
    return ContractValidationReport()


@pytest.fixture(scope="session", autouse=True)
def contract_validation_summary(request, contract_validation_report):
    """Generate and display contract validation summary after test session."""
    yield
    report = contract_validation_report.generate_report()
    print("\n" + "=" * 80)
    print(report)
    print("=" * 80)


@pytest.fixture
def snapshot_verifier(contract_options, contract_validation_report, request):
    """Provide a snapshot verifier that also records validation results."""

    base_verifier = SnapshotVerifier(snapshot_dir=contract_options["snapshot_dir"])

    class ReportingSnapshotVerifier:
        def compare_with_snapshot(self, name, data, variant="", update_snapshot=False):
            full_update = update_snapshot or contract_options["update_snapshots"]
            result = base_verifier.compare_with_snapshot(name, data, variant, update_snapshot=full_update)

            test_id = request.node.nodeid
            validation_type = name.split(".")[-1] if "." in name else "unknown"

            contract_validation_report.add_result(test_id, validation_type, result)
            return result

        def __getattr__(self, attr):
            return getattr(base_verifier, attr)

    return ReportingSnapshotVerifier()
