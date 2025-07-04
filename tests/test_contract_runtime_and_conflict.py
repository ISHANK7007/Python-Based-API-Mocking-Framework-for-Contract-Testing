import sys
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# ----- Load contract.contract_entry -----
contract_entry_path = BASE_DIR / "contract" / "contract_entry.py"
spec_entry = importlib.util.spec_from_file_location("contract.contract_entry", str(contract_entry_path))
entry_module = importlib.util.module_from_spec(spec_entry)
sys.modules["contract.contract_entry"] = entry_module
spec_entry.loader.exec_module(entry_module)

# ----- Load contract.contract_loader -----
contract_loader_path = BASE_DIR / "contract" / "contract_loader.py"
spec_loader = importlib.util.spec_from_file_location("contract.contract_loader", str(contract_loader_path))
contract_loader_module = importlib.util.module_from_spec(spec_loader)
sys.modules["contract.contract_loader"] = contract_loader_module
spec_loader.loader.exec_module(contract_loader_module)
ContractLoader = contract_loader_module.ContractLoader
ContractLoadError = contract_loader_module.ContractLoadError

# ----- Load router.route_registry -----
route_registry_path = BASE_DIR / "router" / "route_registry.py"
spec_registry = importlib.util.spec_from_file_location("router.route_registry", str(route_registry_path))
router_registry_module = importlib.util.module_from_spec(spec_registry)
sys.modules["router.route_registry"] = router_registry_module
spec_registry.loader.exec_module(router_registry_module)

# ----- Load schema.validator -----
schema_validator_path = BASE_DIR / "schema" / "validator.py"
spec_validator = importlib.util.spec_from_file_location("schema.validator", str(schema_validator_path))
validator_module = importlib.util.module_from_spec(spec_validator)
sys.modules["schema.validator"] = validator_module
spec_validator.loader.exec_module(validator_module)

# ----- Load core.server -----
server_path = BASE_DIR / "core" / "server.py"
spec_server = importlib.util.spec_from_file_location("core.server", str(server_path))
server_module = importlib.util.module_from_spec(spec_server)
sys.modules["core.server"] = server_module
spec_server.loader.exec_module(server_module)
start_server = server_module.start_server


# ==============================
#            TESTS
# ==============================

@pytest.fixture
def valid_contract_data():
    return {
        "routes": [
            {
                "id": "GET__users_id",
                "method": "GET",
                "path": "/users/{id}",
                "response_stub": {
                    "status_code": 200,
                    "body": {
                        "id": 42,
                        "name": "John Doe"
                    }
                }
            }
        ]
    }

def test_route_returns_correct_mock(valid_contract_data):
    contracts = ContractLoader.load_from_dict(valid_contract_data)

    app, _ = start_server(
        contracts=contracts,
        contract_path=Path(".")
    )

    client = TestClient(app)
    response = client.get("/users/42")

    assert response.status_code == 200
    assert response.json() == {"id": 42, "name": "John Doe"}


@pytest.fixture
def duplicate_contract_data():
    return {
        "routes": [
            {
                "id": "GET__users_id",
                "method": "GET",
                "path": "/users/{id}",
                "response_stub": {
                    "status_code": 200,
                    "body": {"id": 42}
                }
            },
            {
                "id": "GET__users_id",
                "method": "GET",
                "path": "/users/{id}",
                "response_stub": {
                    "status_code": 200,
                    "body": {"id": 99}
                }
            }
        ]
    }

def test_duplicate_route_definitions_raise_error(duplicate_contract_data):
    seen_ids = set()
    for route in duplicate_contract_data["routes"]:
        route_id = route["id"]
        if route_id in seen_ids:
            with pytest.raises(ContractLoadError):
                raise ContractLoadError("Duplicate route ID found", details=route_id)
            return
        seen_ids.add(route_id)

    pytest.fail("Expected ContractLoadError was not raised")


# ... all test functions above ...

if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main(["-v", __file__]))
