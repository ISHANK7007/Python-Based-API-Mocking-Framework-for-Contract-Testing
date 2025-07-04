from flask import Flask, request, jsonify
import yaml
import os

# Import your internal components (adjust these paths as needed)
from contract.contract_version_manager import ContractVersionManager
from verifier.contract_test_decorator import VersionAwareContractEnforcer

app = Flask(__name__)

# Initialize the contract version manager
version_manager = ContractVersionManager()

# Load contract versions (graceful fallback)
contracts_path = 'contracts'
for version_file in ['v1.0.0.yaml', 'v2.0.0.yaml']:
    version = version_file.replace('.yaml', '')
    path = os.path.join(contracts_path, version_file)
    if os.path.exists(path):
        with open(path, 'r') as f:
            version_manager.add_version(version, yaml.safe_load(f))
    else:
        print(f"Warning: Contract file {version_file} not found")

# Initialize the contract enforcer
enforcer = VersionAwareContractEnforcer(version_manager)

# Create a convenience decorator factory
def validate_contract(version='latest', strict=False):
    def decorator(func):
        return enforcer.validate_contract(version=version, strict=strict)(func)
    return decorator

# Example routes

@app.route('/api/v1/users/<id>', methods=['GET'])
@validate_contract(version='v1.0.0')
def get_user_v1(id):
    return jsonify({
        'id': id,
        'name': 'John Doe',
        'email': 'john@example.com'
    })

@app.route('/api/v2/users/<id>', methods=['GET'])
@validate_contract(version='v2.0.0')
def get_user_v2(id):
    return jsonify({
        'id': id,
        'name': 'John Doe',
        'email': 'john@example.com',
        'profile': {
            'bio': 'Software engineer',
            'location': 'San Francisco'
        }
    })

@app.route('/api/v2/users/search', methods=['GET'])
@validate_contract(version='v2.0.0')
def search_users():
    query = request.args.get('query', '')
    return jsonify([
        {
            'id': '123',
            'name': 'John Doe',
            'email': 'john@example.com'
        }
    ])

@app.route('/api/v2/users', methods=['GET'])
@validate_contract(version='v2.0.0')
def list_users():
    query = request.args.get('search', '')
    return jsonify([
        {
            'id': '123',
            'name': 'John Doe',
            'email': 'john@example.com',
            'profile': {
                'bio': 'Software engineer',
                'location': 'San Francisco'
            }
        }
    ])

# Run the Flask app
if __name__ == "__main__":
    app.run(debug=True)

# CLI examples:
# 1. Compare contracts and check for deprecated routes:
#    contract-diff contracts/v1.0.0.yaml contracts/v2.0.0.yaml --check-deprecated
#
# 2. Generate a deprecation report with usage data:
#    contract-diff contracts/v1.0.0.yaml contracts/v2.0.0.yaml --deprecation-report
