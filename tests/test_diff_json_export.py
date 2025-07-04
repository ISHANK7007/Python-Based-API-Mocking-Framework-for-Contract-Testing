
import unittest
import tempfile
import os
import yaml

from contract.contract_entry import ContractEntry, Route, Response
from contract.contract_diff_types import ChangeType
from contract.compatibility_checker import compatibility_check


from contract.contract_differ import ChangeType, OptimizedContractDiffer
from contract.contract_loader import ContractLoader

from contract.contract_diff_formatter import EnhancedDiffFormatter
from contract.contract_diff_types import SeverityGroupedFormatter


from schema.validator import SchemaValidator
from schema.validator import SchemaCompatibilityValidator  # If it's defined here

from core.diff_severity_grouping import Severity

from core.diff_optimizer import OptimizedContractDiffer


class TestContractDiffClassification(unittest.TestCase):
    def setUp(self):
        self.differ = OptimizedContractDiffer()
        self.base_contract = self._create_base_contract()

    def _create_base_contract(self):
        contract = ContractEntry(
            title="Test API",
            version="1.0.0",
            description="Test API for diffing tests",
            routes=[],
            metadata={"test": True}
        )

        contract.routes.append(Route(
            path="/users/{id}",
            method="GET",
            description="Get user by ID",
            request_schema={"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
            responses=[
                Response(200, "User", "application/json", {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "name": {"type": "string"}, "email": {"type": "string"}},
                    "required": ["id", "name", "email"]
                }),
                Response(404, "Not Found", "application/json", {
                    "type": "object",
                    "properties": {"error": {"type": "string"}},
                    "required": ["error"]
                })
            ]
        ))

        contract.routes.append(Route(
            path="/products",
            method="GET",
            description="List products",
            request_schema={"type": "object", "properties": {"category": {"type": "string"}, "page": {"type": "integer"}}},
            responses=[
                Response(200, "OK", "application/json", {
                    "type": "object",
                    "properties": {
                        "products": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "price": {"type": "number"}
                                },
                                "required": ["id", "name", "price"]
                            }
                        }
                    },
                    "required": ["products"]
                })
            ]
        ))

        contract.routes.append(Route(
            path="/orders",
            method="POST",
            description="Create order",
            request_schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "product_ids": {"type": "array", "items": {"type": "string"}},
                    "quantity": {"type": "string"}
                },
                "required": ["user_id", "product_ids"]
            },
            responses=[
                Response(201, "Created", "application/json", {
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}, "status": {"type": "string"}},
                    "required": ["order_id", "status"]
                })
            ]
        ))

        return contract

    def _save_contract_to_temp_file(self, contract):
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode='w') as temp:
            yaml.dump(contract.to_dict(), temp, sort_keys=False)
            return temp.name

    def test_deleted_route_breaking(self):
        modified = ContractEntry(**self.base_contract.to_dict())
        modified.routes = [r for r in modified.routes if r.path != "/users/{id}"]

        diff = self.differ.diff_contracts(self.base_contract, modified)
        summaries = EnhancedDiffFormatter().generate_change_summaries(diff)

        deleted = [s for s in summaries if s.change_type == ChangeType.ROUTE_REMOVED and s.path == "/users/{id}"]
        self.assertTrue(deleted and deleted[0].is_breaking)

    def test_added_optional_field_non_breaking(self):
        modified = ContractEntry(**self.base_contract.to_dict())
        for r in modified.routes:
            if r.path == "/products":
                r.request_schema["properties"]["sort_by"] = {
                    "type": "string",
                    "description": "Field to sort",
                    "enum": ["name", "price"]
                }

        diff = self.differ.diff_contracts(self.base_contract, modified)
        summaries = EnhancedDiffFormatter().generate_change_summaries(diff)

        added = [s for s in summaries if s.change_type == ChangeType.REQUEST_FIELD_ADDED and "sort_by" in str(s.details)]
        self.assertTrue(added and not added[0].is_breaking)

    def test_changed_field_type_breaking(self):
        modified = ContractEntry(**self.base_contract.to_dict())
        for r in modified.routes:
            if r.path == "/orders":
                r.request_schema["properties"]["quantity"]["type"] = "integer"

        diff = self.differ.diff_contracts(self.base_contract, modified)
        summaries = EnhancedDiffFormatter().generate_change_summaries(diff)

        modified_type = [s for s in summaries if s.change_type == ChangeType.REQUEST_FIELD_MODIFIED]
        self.assertTrue(modified_type and modified_type[0].is_breaking)

    def test_schema_type_incompatibility(self):
        old_schema = {"type": "object", "properties": {"quantity": {"type": "string"}}}
        new_schema = {"type": "object", "properties": {"quantity": {"type": "integer"}}}

        data = {"quantity": "5"}
        compat = SchemaCompatibilityValidator()
        schema_validator = SchemaValidator()

        analysis = compat.analyze_compatibility(old_schema, new_schema)
        self.assertFalse(analysis["is_backwards_compatible"])
        self.assertTrue(any(c["type"] == "property_type_change" for c in analysis["breaking_changes"]))

        valid1, _ = schema_validator.validate(data, old_schema)
        valid2, errors = schema_validator.validate(data, new_schema)
        self.assertTrue(valid1)
        self.assertFalse(valid2)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
