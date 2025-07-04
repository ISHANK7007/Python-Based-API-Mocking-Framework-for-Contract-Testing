from pathlib import Path
import tempfile

from contract.contract_loader_unified import EnhancedContractLoader
from contract.contract_conflict import ContractConflictError

def test_duplicate_detection():
    """
    Test function to demonstrate the duplicate detection functionality.
    """
    yaml_content = """
routes:
  - path: /users
    method: GET
    response_stub:
      status_code: 200
      body: []

  - path: /users/{id}
    method: GET
    path_parameters:
      - name: id
        type: string
    response_stub:
      status_code: 200
      body: {"id": "{id}"}

  - path: /users
    method: GET
    response_stub:
      status_code: 200
      body: {"message": "This is a duplicate route"}

  - path: /users
    method: POST
    request_body_schema:
      type: object
      properties:
        name: {type: string}
    response_stub:
      status_code: 201
      body: {"id": "123"}

  - path: /users/{id}
    method: GET
    path_parameters:
      - name: id
        type: string
    response_stub:
      status_code: 404
      body: {"error": "Not found"}
"""

    with tempfile.NamedTemporaryFile(suffix='.yaml', mode='w+', delete=True) as temp_file:
        temp_file.write(yaml_content)
        temp_file.flush()

        print(f"Testing duplicate detection with: {temp_file.name}\n")

        # Test with duplicates disallowed
        try:
            EnhancedContractLoader.load_from_file(Path(temp_file.name), allow_duplicates=False)
            print("❌ Duplicate detection failed — no conflict raised")
        except ContractConflictError as e:
            print("✅ Successfully detected duplicate routes:")
            for conflict in e.conflicts:
                lines = ', '.join(map(str, conflict['lines']))
                print(f"  - {conflict['method']} {conflict['path']} (lines: {lines})")

        # Test with duplicates allowed
        print("\nTesting with duplicates allowed:")
        contracts = EnhancedContractLoader.load_from_file(Path(temp_file.name), allow_duplicates=True)
        print(f"✅ Loaded {len(contracts)} contracts (including duplicates)")
