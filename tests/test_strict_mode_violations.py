import pytest
import functools
from pathlib import Path

def contract_versions(*versions):
    """
    Decorator to parametrize tests with multiple contract versions.
    Supports optional custom IDs using "name=version" syntax.
    """
    # Flatten single list input
    if len(versions) == 1 and isinstance(versions[0], (list, tuple)):
        versions = versions[0]

    ids = []
    processed_versions = []

    for v in versions:
        if "=" in str(v):
            id_name, version = v.split("=", 1)
            ids.append(id_name)
            processed_versions.append(version)
        else:
            ids.append(f"contract:{v}")
            processed_versions.append(v)

    return pytest.mark.parametrize(
        "contract_version", processed_versions,
        ids=ids,
        indirect=True
    )


def contract_major_versions(name, *major_versions):
    """
    Decorator to parametrize test with latest version of each given major version.
    Assumes contract files are stored in `tests/contracts/` with names like users-v1.2.3.yaml
    """
    def get_latest_minor_for_major(contracts_dir: Path, name: str, major: int) -> str:
        pattern = f"{name}-v{major}.*.*.yaml"
        matches = sorted(contracts_dir.glob(pattern))
        if not matches:
            raise FileNotFoundError(f"No contracts found for {name} v{major}")
        return matches[-1].stem  # return filename without extension

    def decorator(test_func):
        @functools.wraps(test_func)
        def wrapper(request, *args, **kwargs):
            contracts_dir = Path("tests/contracts")  # or configurable base path
            versions = [
                get_latest_minor_for_major(contracts_dir, name, major)
                for major in major_versions
            ]

            mark = pytest.mark.parametrize(
                "contract_version", versions,
                ids=[f"{name}-v{v}" for v in major_versions],
                indirect=True
            )
            decorated = mark(test_func)
            return decorated(request, *args, **kwargs)

        return wrapper

    return decorator
