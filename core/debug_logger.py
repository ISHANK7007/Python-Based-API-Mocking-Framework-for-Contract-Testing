import unittest
import json
import tempfile
import os
import requests
import time
import yaml
import subprocess
import signal
from typing import Dict, Any, List, Optional, Union


class ResponseVariantIntegrationTest(unittest.TestCase):
    """Integration test for response variants with different header conditions"""
    
    @classmethod
    def setUpClass(cls):
        """Create a mock server with test contract and start it"""
        # Create a temporary contract file
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.contract_path = os.path.join(cls.temp_dir.name, "test_contract.yaml")
        
        # Define test contract with 3 variants and a fallback
        contract_yaml = """
        - id: product-variant-test
          method: GET
          path: /api/products/{productId}
          path_parameters:
            - name: productId
              schema:
                type: string
              required: true
          response:
            variants:
              - condition: headers['X-Region'] == 'EU'
                response:
                  status: 200
                  headers:
                    Content-Type: application/json
                    X-Selected-Variant: "eu-region"
                  body:
                    productId: "{{ path_params.productId }}"
                    name: "EU Product {{ path_params.productId }}"
                    price: 100
                    currency: "EUR"
                    tax: 20
                    region: "EU"
              
              - condition: headers['X-User-Role'] == 'admin'
                response:
                  status: 200
                  headers:
                    Content-Type: application/json
                    X-Selected-Variant: "admin-view"
                  body:
                    productId: "{{ path_params.productId }}"
                    name: "Product {{ path_params.productId }}"
                    price: 80
                    currency: "USD"
                    cost: 50
                    margin: 30
                    hidden: true
              
              - condition: headers['Accept-Language'] contains 'es'
                response:
                  status: 200
                  headers:
                    Content-Type: application/json
                    Content-Language: es
                    X-Selected-Variant: "spanish"
                  body:
                    productId: "{{ path_params.productId }}"
                    name: "Producto {{ path_params.productId }}"
                    precio: 90
                    moneda: "USD"
            
            fallback_response:
              status: 200
              headers:
                Content-Type: application/json
                X-Selected-Variant: "fallback"
              body:
                productId: "{{ path_params.productId }}"
                name: "Product {{ path_params.productId }}"
                price: 90
                currency: "USD"
                
        - id: error-cases
          method: GET
          path: /api/products/{productId}/error
          path_parameters:
            - name: productId
              schema:
                type: string
              required: true
          response:
            variants:
              - condition: headers['X-Error'] == 'not-found'
                response:
                  status: 404
                  headers:
                    Content-Type: application/json
                  body:
                    error: "Product not found"
                    code: "PRODUCT_NOT_FOUND"
                    productId: "{{ path_params.productId }}"
              
              - condition: headers['X-Error'] == 'forbidden'
                response:
                  status: 403
                  headers:
                    Content-Type: application/json
                  body:
                    error: "Access forbidden"
                    code: "ACCESS_DENIED"
            
            fallback_response:
              status: 400
              headers:
                Content-Type: application/json
              body:
                error: "Bad request"
                code: "BAD_REQUEST"
        """
        
        # Write contract to file
        with open(cls.contract_path, 'w') as f:
            f.write(contract_yaml)
        
        # Start mock server
        cls.server_port = 8765  # Use a specific port for testing
        cls.server_process = subprocess.Popen([
            "python", "-m", "mockapi", "serve",
            "--contract", cls.contract_path,
            "--port", str(cls.server_port),
            "--host", "127.0.0.1"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for server to start
        cls.base_url = f"http://127.0.0.1:{cls.server_port}"
        cls._wait_for_server()
    
    @classmethod
    def tearDownClass(cls):
        """Stop the mock server and clean up temporary files"""
        if hasattr(cls, 'server_process'):
            # Stop the server
            cls.server_process.send_signal(signal.SIGTERM)
            cls.server_process.wait(timeout=5)
        
        if hasattr(cls, 'temp_dir'):
            cls.temp_dir.cleanup()
    
    @classmethod
    def _wait_for_server(cls):
        """Wait for the server to become available"""
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"{cls.base_url}/mockapi/health", timeout=1)
                if response.status_code == 200:
                    return
            except Exception:
                pass
            
            time.sleep(0.5)
        
        raise Exception(f"Server did not start within {max_attempts} attempts")
    
    def test_eu_region_variant(self):
        """Test the EU region variant is selected with X-Region header"""
        # Make request with EU region header
        product_id = "123"
        headers = {"X-Region": "EU"}
        
        response = requests.get(
            f"{self.base_url}/api/products/{product_id}",
            headers=headers
        )
        
        # Validate response
        self.assertEqual(200, response.status_code, "Status code should be 200")
        self.assertEqual("eu-region", response.headers.get("X-Selected-Variant"),
                        "EU variant should be selected")
        
        data = response.json()
        self.assertEqual(product_id, data["productId"], "Product ID should match")
        self.assertEqual("EU Product 123", data["name"], "Should have EU product name")
        self.assertEqual(100, data["price"], "Price should match EU variant")
        self.assertEqual("EUR", data["currency"], "Currency should be EUR for EU variant")
        self.assertEqual(20, data["tax"], "Should include EU tax")
        self.assertEqual("EU", data["region"], "Should specify EU region")
    
    def test_admin_role_variant(self):
        """Test the admin role variant is selected with X-User-Role header"""
        # Make request with admin role header
        product_id = "456"
        headers = {"X-User-Role": "admin"}
        
        response = requests.get(
            f"{self.base_url}/api/products/{product_id}",
            headers=headers
        )
        
        # Validate response
        self.assertEqual(200, response.status_code, "Status code should be 200")
        self.assertEqual("admin-view", response.headers.get("X-Selected-Variant"),
                        "Admin variant should be selected")
        
        data = response.json()
        self.assertEqual(product_id, data["productId"], "Product ID should match")
        self.assertEqual("Product 456", data["name"], "Should have standard product name")
        self.assertEqual(80, data["price"], "Price should match admin variant")
        self.assertEqual(50, data["cost"], "Should include cost for admin view")
        self.assertEqual(30, data["margin"], "Should include margin for admin view")
        self.assertEqual(True, data["hidden"], "Should show hidden flag for admin")
    
    def test_spanish_language_variant(self):
        """Test the Spanish language variant is selected with Accept-Language header"""
        # Make request with Spanish language header
        product_id = "789"
        headers = {"Accept-Language": "es-ES,es;q=0.9"}
        
        response = requests.get(
            f"{self.base_url}/api/products/{product_id}",
            headers=headers
        )
        
        # Validate response
        self.assertEqual(200, response.status_code, "Status code should be 200")
        self.assertEqual("spanish", response.headers.get("X-Selected-Variant"),
                        "Spanish variant should be selected")
        self.assertEqual("es", response.headers.get("Content-Language"),
                        "Content-Language should be Spanish")
        
        data = response.json()
        self.assertEqual(product_id, data["productId"], "Product ID should match")
        self.assertEqual("Producto 789", data["name"], "Should have Spanish product name")
        self.assertEqual(90, data["precio"], "Should use Spanish field name 'precio'")
        self.assertEqual("USD", data["moneda"], "Should use Spanish field name 'moneda'")
    
    def test_fallback_response(self):
        """Test the fallback response is selected when no variant conditions match"""
        # Make request without any matching headers
        product_id = "999"
        headers = {"User-Agent": "IntegrationTest/1.0"}
        
        response = requests.get(
            f"{self.base_url}/api/products/{product_id}",
            headers=headers
        )
        
        # Validate response
        self.assertEqual(200, response.status_code, "Status code should be 200")
        self.assertEqual("fallback", response.headers.get("X-Selected-Variant"),
                        "Fallback should be selected")
        
        data = response.json()
        self.assertEqual(product_id, data["productId"], "Product ID should match")
        self.assertEqual("Product 999", data["name"], "Should have standard product name")
        self.assertEqual(90, data["price"], "Price should match fallback variant")
        self.assertEqual("USD", data["currency"], "Currency should be USD for fallback")
    
    def test_variant_precedence(self):
        """Test that variants are evaluated in order (first match wins)"""
        # Request with headers matching multiple variants
        product_id = "555"
        headers = {
            "X-Region": "EU",           # Matches first variant
            "X-User-Role": "admin",     # Matches second variant
            "Accept-Language": "es-ES"  # Matches third variant
        }
        
        response = requests.get(
            f"{self.base_url}/api/products/{product_id}",
            headers=headers
        )
        
        # First matching variant should win
        self.assertEqual(200, response.status_code, "Status code should be 200")
        self.assertEqual("eu-region", response.headers.get("X-Selected-Variant"),
                        "First matching variant (EU) should be selected")
        
        data = response.json()
        self.assertEqual("EU", data["region"], "Should specify EU region")
        self.assertNotIn("margin", data, "Should not include admin-only fields")
    
    def test_case_insensitive_headers(self):
        """Test that header matching is case-insensitive"""
        product_id = "789"
        # Use lowercase header name
        headers = {"x-user-role": "admin"}
        
        response = requests.get(
            f"{self.base_url}/api/products/{product_id}",
            headers=headers
        )
        
        self.assertEqual(200, response.status_code, "Status code should be 200")
        self.assertEqual("admin-view", response.headers.get("X-Selected-Variant"),
                        "Admin variant should be selected despite lowercase header")
    
    def test_error_response_not_found(self):
        """Test error response variant for not found case"""
        product_id = "missing"
        headers = {"X-Error": "not-found"}
        
        response = requests.get(
            f"{self.base_url}/api/products/{product_id}/error",
            headers=headers
        )
        
        self.assertEqual(404, response.status_code, "Status code should be 404")
        data = response.json()
        self.assertEqual("PRODUCT_NOT_FOUND", data["code"], "Error code should match")
        self.assertEqual(product_id, data["productId"], "Should include product ID in error")
    
    def test_error_response_forbidden(self):
        """Test error response variant for forbidden case"""
        product_id = "secret"
        headers = {"X-Error": "forbidden"}
        
        response = requests.get(
            f"{self.base_url}/api/products/{product_id}/error",
            headers=headers
        )
        
        self.assertEqual(403, response.status_code, "Status code should be 403")
        data = response.json()
        self.assertEqual("ACCESS_DENIED", data["code"], "Error code should match")
    
    def test_error_response_fallback(self):
        """Test error response fallback for unknown error case"""
        product_id = "invalid"
        headers = {"X-Error": "unknown"}  # Doesn't match any variant
        
        response = requests.get(
            f"{self.base_url}/api/products/{product_id}/error",
            headers=headers
        )
        
        self.assertEqual(400, response.status_code, "Status code should be 400 (fallback)")
        data = response.json()
        self.assertEqual("BAD_REQUEST", data["code"], "Error code should match fallback")


if __name__ == "__main__":
    unittest.main()