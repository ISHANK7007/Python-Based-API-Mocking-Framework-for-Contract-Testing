import pytest
import json
import re
import os
from typing import Dict, List, Any, Set, Optional, Tuple

class TestCoverageAnalyzer:
    """
    Analyzes test coverage for API endpoints.
    """
    
    def __init__(self):
        self.route_coverage = {}  # Maps route keys to coverage info
        self.test_routes = {}  # Maps test IDs to routes tested
    
    def load_coverage_data(self, coverage_file: str):
        """
        Load API test coverage data from a file.
        
        Args:
            coverage_file: Path to coverage data file
            
        Returns:
            Number of routes with coverage data
        """
        with open(coverage_file, 'r') as f:
            coverage_data = json.load(f)
            
            # Process each test's coverage info
            for test_id, test_info in coverage_data.items():
                self._process_test_coverage(test_id, test_info)
        
        return len(self.route_coverage)
    
    def _process_test_coverage(self, test_id: str, test_info: Dict[str, Any]):
        """Process coverage data for a single test."""
        # Extract routes tested
        routes_tested = set()
        
        for http_request in test_info.get('http_requests', []):
            method = http_request.get('method', '').upper()
            path = http_request.get('path', '')
            
            if method and path:
                # Normalize the path to match contract patterns
                path = self._normalize_path(path)
                route_key = f"{method}:{path}"
                routes_tested.add(route_key)
                
                # Update route coverage info
                if route_key not in self.route_coverage:
                    self.route_coverage[route_key] = {
                        'path': path,
                        'method': method,
                        'tests': set(),
                        'status_codes_tested': set(),
                        'parameter_variations': set(),
                        'last_tested': test_info.get('timestamp', ''),
                        'request_count': 0
                    }
                
                # Add test coverage details
                self.route_coverage[route_key]['tests'].add(test_id)
                self.route_coverage[route_key]['request_count'] += 1
                
                if 'status' in http_request:
                    self.route_coverage[route_key]['status_codes_tested'].add(
                        str(http_request['status'])
                    )
                
                # Track parameter variations
                self._track_parameter_variations(route_key, http_request)
        
        # Store test-to-routes mapping
        self.test_routes[test_id] = routes_tested
    
    def _normalize_path(self, path: str) -> str:
        """
        Convert concrete paths to template paths.
        
        E.g., /users/123 -> /users/{id}
        """
        # Common ID patterns (should match the same patterns in UsageDataProcessor)
        patterns = [
            (r'/users/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/users/{id}'),
            (r'/users/\d+', '/users/{id}'),
            (r'/products/[0-9a-f]{24}', '/products/{id}'),  # MongoDB ObjectId
            (r'/orders/\d{4}-\d{2}-\d{2}-\d+', '/orders/{order_date_id}'),
        ]
        
        result = path
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
        
        return result
    
    def _track_parameter_variations(self, route_key: str, request: Dict[str, Any]):
        """Track different parameter variations used in tests."""
        # Extract query parameters
        if 'query' in request and request['query']:
            query_str = '&'.join(f"{k}={v}" for k, v in request['query'].items())
            self.route_coverage[route_key]['parameter_variations'].add(f"query:{query_str}")
        
        # Extract body parameters for relevant methods
        if request.get('method', '').upper() in ('POST', 'PUT', 'PATCH'):
            if 'body' in request:
                body = request['body']
                if isinstance(body, dict):
                    body_str = json.dumps(body, sort_keys=True)
                    self.route_coverage[route_key]['parameter_variations'].add(f"body:{body_str}")
    
    def get_route_coverage(self, method: str, path: str) -> Optional[Dict[str, Any]]:
        """
        Get test coverage for a specific route.
        
        Args:
            method: HTTP method
            path: Route path
            
        Returns:
            Coverage information or None if not tested
        """
        route_key = f"{method.upper()}:{path}"
        
        if route_key not in self.route_coverage:
            return None
            
        coverage = self.route_coverage[route_key]
        
        # Convert sets to lists for serialization
        return {
            'path': coverage['path'],
            'method': coverage['method'],
            'test_count': len(coverage['tests']),
            'status_codes_tested': list(coverage['status_codes_tested']),
            'parameter_variations_count': len(coverage['parameter_variations']),
            'last_tested': coverage['last_tested'],
            'request_count': coverage['request_count']
        }
    
    def get_affected_tests(self, routes: List[str]) -> List[str]:
        """
        Find tests that would be affected by changes to the given routes.
        
        Args:
            routes: List of route keys affected by changes
            
        Returns:
            List of test IDs that test the affected routes
        """
        affected_tests = set()
        routes_set = set(routes)
        
        for test_id, test_routes in self.test_routes.items():
            if test_routes & routes_set:
                affected_tests.add(test_id)
        
        return sorted(affected_tests)
    
    def get_coverage_gap_report(self, contract_routes: List[str]) -> Dict[str, Any]:
        """
        Find routes in the contract that have no or insufficient test coverage.
        
        Args:
            contract_routes: List of route keys from the contract
            
        Returns:
            Report on coverage gaps
        """
        contract_set = set(contract_routes)
        covered_set = set(self.route_coverage.keys())
        
        uncovered_routes = contract_set - covered_set
        poor_coverage = []
        
        # Check for routes with limited coverage
        for route_key in (contract_set & covered_set):
            coverage = self.route_coverage[route_key]
            
            # Define criteria for poor coverage
            if (len(coverage['status_codes_tested']) < 2 or
                len(coverage['parameter_variations']) < 2 or
                len(coverage['tests']) < 2):
                
                poor_coverage.append({
                    'route_key': route_key,
                    'path': coverage['path'],
                    'method': coverage['method'],
                    'test_count': len(coverage['tests']),
                    'status_codes_tested': list(coverage['status_codes_tested']),
                    'parameter_variations_count': len(coverage['parameter_variations'])
                })
        
        return {
            'total_routes_in_contract': len(contract_routes),
            'uncovered_routes_count': len(uncovered_routes),
            'poor_coverage_count': len(poor_coverage),
            'coverage_percentage': ((len(contract_set) - len(uncovered_routes)) / 
                                   len(contract_set) * 100) if contract_set else 0,
            'uncovered_routes': [route for route in uncovered_routes],
            'poor_coverage_routes': poor_coverage
        }