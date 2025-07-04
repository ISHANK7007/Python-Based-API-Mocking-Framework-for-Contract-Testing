import unittest
import threading
import os
import json
import time
import tempfile
import requests
import yaml
import uvicorn
from contextlib import contextmanager

# Import from our mock API package
from core.server_factory import create_server
from contract.contract_loader import ContractLoader

class MockServerIntegrationTest(unittest.TestCase):
    """Integration test for the mock API server."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.contract_path = os.path.join(cls.temp_dir.name, "test_contract.yaml")
        sample_contract = {
            "routes": [
                {
                    "method": "GET",
                    "path": "/users/{userId}",
                    "path_parameters": [{"name": "userId", "type": "string"}],
                    "response_stub": {
                        "status_code": 200,
                        "headers": {
                            "Content-Type": "application/json",
                            "X-Test-Header": "integration-test"
                        },
                        "body": {
                            "id": "{userId}",
                            "name": "Test User {userId}",
                            "email": "user{userId}@example.com"
                        }
                    }
                },
                {
                    "method": "POST",
                    "path": "/users",
                    "request_body_schema": {
                        "type": "object",
                        "required": ["name", "email"],
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string", "format": "email"},
                            "age": {"type": "integer", "minimum": 18}
                        }
                    },
                    "response_stub": {
                        "status_code": 201,
                        "headers": {
                            "Content-Type": "application/json",
                            "Location": "/users/456"
                        },
                        "body": {
                            "id": "456",
                            "name": "{request.body.name}",
                            "email": "{request.body.email}",
                            "created_at": "{now}"
                        }
                    }
                }
            ]
        }
        with open(cls.contract_path, 'w') as f:
            yaml.dump(sample_contract, f)

        cls.port = 12345
        cls.host = "127.0.0.1"
        cls.base_url = f"http://{cls.host}:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    @contextmanager
    def run_server_in_thread(self, use_trie=True, strict_validation=True):
        contracts = ContractLoader.load_from_file(self.contract_path)
        app, shutdown_event = create_server(
            contracts=contracts,
            use_trie=use_trie,
            strict_validation=strict_validation
        )

        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        server = uvicorn.Server(config)

        server_exception = None

        def run_server():
            try:
                server.run()
            except Exception as e:
                nonlocal server_exception
                server_exception = e

        thread = threading.Thread(target=run_server)
        thread.daemon = True
        thread.start()

        time.sleep(1)

        try:
            if server_exception:
                raise server_exception

            health_check_url = f"{self.base_url}/health"
            retries = 5
            while retries > 0:
                try:
                    response = requests.get(health_check_url, timeout=1)
                    if response.status_code == 200:
                        break
                except (requests.ConnectionError, requests.Timeout):
                    pass
                time.sleep(0.5)
                retries -= 1

            if retries == 0:
                raise Exception("Server did not start properly")

            yield
        finally:
            shutdown_event.set()
            thread.join(timeout=5)
            if thread.is_alive():
                print("Warning: Server did not shut down gracefully")

    def test_retrieve_user(self):
        with self.run_server_in_thread():
            user_id = "123"
            url = f"{self.base_url}/users/{user_id}"
            response = requests.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Content-Type"], "application/json")
            self.assertEqual(response.headers["X-Test-Header"], "integration-test")
            data = response.json()
            self.assertEqual(data["id"], user_id)
            self.assertEqual(data["name"], f"Test User {user_id}")
            self.assertEqual(data["email"], f"user{user_id}@example.com")

    def test_create_user(self):
        with self.run_server_in_thread():
            url = f"{self.base_url}/users"
            user_data = {
                "name": "John Doe",
                "email": "john@example.com",
                "age": 25
            }
            response = requests.post(url, json=user_data, headers={"Content-Type": "application/json"})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.headers["Content-Type"], "application/json")
            self.assertEqual(response.headers["Location"], "/users/456")
            data = response.json()
            self.assertEqual(data["id"], "456")
            self.assertEqual(data["name"], user_data["name"])
            self.assertEqual(data["email"], user_data["email"])
            self.assertIn("created_at", data)

    def test_strict_validation_rejects_extra_fields(self):
        with self.run_server_in_thread(strict_validation=True):
            url = f"{self.base_url}/users"
            user_data = {
                "name": "John Doe",
                "email": "john@example.com",
                "age": 25,
                "extra_field": "should be rejected"
            }
            response = requests.post(url, json=user_data, headers={"Content-Type": "application/json"})
            self.assertEqual(response.status_code, 400)
            data = response.json()
            self.assertIn("error", data)
            self.assertIn("extra_field", str(data["error"]))

    def test_performance_comparison(self):
        results = {}

        with self.run_server_in_thread(use_trie=True):
            start_time = time.time()
            for i in range(100):
                user_id = str(i)
                url = f"{self.base_url}/users/{user_id}"
                response = requests.get(url)
                self.assertEqual(response.status_code, 200)
            trie_time = time.time() - start_time
            results["trie_time"] = trie_time

        with self.run_server_in_thread(use_trie=False):
            start_time = time.time()
            for i in range(100):
                user_id = str(i)
                url = f"{self.base_url}/users/{user_id}"
                response = requests.get(url)
                self.assertEqual(response.status_code, 200)
            regex_time = time.time() - start_time
            results["regex_time"] = regex_time

        print(f"\nPerformance comparison:")
        print(f"  Trie-based routing: {trie_time:.4f}s")
        print(f"  Regex-based routing: {regex_time:.4f}s")
        print(f"  Speedup factor: {regex_time/trie_time:.2f}x")
        self.assertLess(trie_time, regex_time * 1.5,
                        "Trie-based routing should be at least as fast as regex-based routing")

        return results


if __name__ == "__main__":
    unittest.main()
