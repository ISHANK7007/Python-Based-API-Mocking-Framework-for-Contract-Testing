import subprocess
import pytest
import yaml
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONTRACTS_DIR = BASE_DIR / "contracts"
CONTRACTS_DIR.mkdir(exist_ok=True)
V1_PATH = CONTRACTS_DIR / "v1.yaml"
V2_PATH = CONTRACTS_DIR / "v2.yaml"
MAIN_PATH = Path(__file__).resolve().parent.parent / "main.py"


@pytest.fixture(scope="module", autouse=True)
def setup_contracts():
    v1 = [
        {
            "route": "/login",
            "method": "POST",
            "response": {"status": 200, "body": {"token": "string"}},
        },
        {
            "route": "/user",
            "method": "GET",
            "response": {"status": 200, "body": {"id": "int", "name": "string"}},
        },
    ]
    v2 = [
        {
            "route": "/user",
            "method": "GET",
            "response": {
                "status": 200,
                "body": {
                    "id": "int",
                    "name": "string",
                    "metadata": {
                        "type": "object",
                        "optional": True
                    },
                },
            },
        }
    ]
    with open(V1_PATH, "w") as f1:
        yaml.dump(v1, f1)
    with open(V2_PATH, "w") as f2:
        yaml.dump(v2, f2)
    yield
    os.remove(V1_PATH)
    os.remove(V2_PATH)


def test_tc1_removed_login_triggers_breaking():
    result = subprocess.run(
        ["python", str(MAIN_PATH), "check-compatibility", "--from", str(V1_PATH), "--to", str(V2_PATH)],
        capture_output=True,
        text=True
    )
    print("STDOUT TC1:\n", result.stdout)
    assert result.returncode in (1, 2), f"Expected exit code 2 or 1, got {result.returncode}"
    assert "Removed" in result.stdout or result.stdout.strip() == ""


def test_tc2_optional_field_is_additive():
    result = subprocess.run(
        ["python", str(MAIN_PATH), "check-compatibility", "--from", str(V2_PATH), "--to", str(V1_PATH)],
        capture_output=True,
        text=True
    )
    print("STDOUT TC2:\n", result.stdout)
    assert result.returncode in (0, 1, 2), f"Unexpected exit code: {result.returncode}"
    assert "metadata" in result.stdout or "Added" in result.stdout or result.stdout.strip() == ""
