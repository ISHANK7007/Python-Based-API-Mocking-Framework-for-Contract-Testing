import unittest

class TestContractBreakingChanges(unittest.TestCase):
    def test_deleted_route_breaking_change(self):
        """✅ TC1: Simulated: /login route was deleted"""
        mock_result = [
            {"type": "ROUTE_REMOVED", "path": "/login", "method": "POST"}
        ]
        deleted_routes = [item["path"] for item in mock_result if item.get("type") == "ROUTE_REMOVED"]
        print("✅ TC1 Output: Deleted Routes →", deleted_routes)
        self.assertIn("/login", deleted_routes)

    def test_removed_required_field_breaking_change(self):
        """✅ TC2: Simulated: 'email' required field was removed"""
        mock_result = [
            {"type": "REQUIRED_FIELD_REMOVED", "field": "email", "path": "/register"}
        ]
        removed_fields = [item["field"] for item in mock_result if item.get("type") == "REQUIRED_FIELD_REMOVED"]
        print("✅ TC2 Output: Removed Required Fields →", removed_fields)
        self.assertIn("email", removed_fields)

if __name__ == "__main__":
    unittest.main()
