from typing import Dict, List, Optional, Set, Tuple, Any, Union
import re
from collections import defaultdict
import logging
from dataclasses import dataclass, field
import time

from contract.contract_entry import ContractEntry
from contract.contract_entry import HttpMethod  # adjust if in different module
from router.route_registry import RouteRegistry

logger = logging.getLogger(__name__)

@dataclass
class RouteMatch:
    """Represents a matched route with extracted parameters"""
    contract: ContractEntry
    path_params: Dict[str, str] = field(default_factory=dict)
    query_params: Dict[str, str] = field(default_factory=dict)
    match_type: str = "exact"  # "exact", "parameterized", or "wildcard"
    match_score: int = 100  # Higher is better/more specific match

class TrieNode:
    """Node in the route trie."""
    
    def __init__(self):
        # Static child segments (exact matches)
        self.children: Dict[str, TrieNode] = {}
        
        # Parameter child (e.g., {id}) - only one per node
        self.param_child: Optional[Tuple[str, TrieNode]] = None
        
        # Wildcard child (e.g., *) - only one per node
        self.wildcard_child: Optional[TrieNode] = None
        
        # Contracts stored at this node (for endpoint matches)
        self.contracts: Dict[HttpMethod, List[ContractEntry]] = defaultdict(list)
        
        # Is this node the end of a valid route?
        self.is_endpoint = False
    
    def __repr__(self):
        return f"TrieNode(children={list(self.children.keys())}, param={self.param_child[0] if self.param_child else None}, wildcard={bool(self.wildcard_child)}, endpoint={self.is_endpoint})"


class TrieRouteRegistry:
    """
    Trie-based route registry for efficient path matching and parameter extraction.
    
    Features:
    - O(k) lookup time where k is the number of path segments
    - Automatic parameter extraction from URLs
    - Support for nested parameter and wildcard paths
    - Prioritizes more specific matches over wildcards
    """
    
    def __init__(self):
        """Initialize the route registry."""
        # Root node of the trie
        self.root = TrieNode()
        
        # Statistics
        self._total_routes = 0
        self._static_routes = 0
        self._parameterized_routes = 0
        self._wildcard_routes = 0
        
        # Parameter pattern for extracting names from paths like {userId}
        self.param_pattern = re.compile(r'{([^{}]+)}')
    
    def _split_path(self, path: str) -> List[str]:
        """
        Split a path into segments.
        
        Args:
            path: URL path to split
            
        Returns:
            List of path segments
        """
        # Remove leading and trailing slashes, then split by /
        return [s for s in path.strip('/').split('/') if s]
    
    def _is_param_segment(self, segment: str) -> bool:
        """Check if a segment is a parameter segment like {id}."""
        return segment.startswith('{') and segment.endswith('}')
    
    def _is_wildcard_segment(self, segment: str) -> bool:
        """Check if a segment is a wildcard segment (*)."""
        return segment == '*'
    
    def _extract_param_name(self, segment: str) -> str:
        """Extract parameter name from a segment like {userId}."""
        match = self.param_pattern.match(segment)
        if match:
            return match.group(1)
        # Fallback if regex fails
        return segment[1:-1]
    
    def _categorize_path(self, path: str) -> Tuple[str, int]:
        """
        Categorize a path and assign a specificity score.
        
        Args:
            path: The path pattern
            
        Returns:
            Tuple of (category, specificity score)
        """
        segments = self._split_path(path)
        
        if any(segment == '*' for segment in segments):
            return "wildcard", 10
            
        param_count = sum(1 for segment in segments if self._is_param_segment(segment))
        
        if param_count > 0:
            # Count segments and parameters for specificity
            static_parts = len(segments) - param_count
            
            # Routes with more static parts are more specific
            specificity = 50 + (static_parts * 10) - param_count
            return "parameterized", specificity
        else:
            return "static", 100
    
    def register(self, contract: ContractEntry) -> None:
        """
        Register a contract entry in the trie.
        
        Args:
            contract: The ContractEntry to register
        """
        path = contract.path
        method = contract.method
        segments = self._split_path(path)
        
        # Determine path category for statistics
        category, _ = self._categorize_path(path)
        
        # Start at the root node
        current = self.root
        
        # Traverse the trie, creating nodes as needed
        for segment in segments:
            if self._is_wildcard_segment(segment):
                # Wildcard segment
                if not current.wildcard_child:
                    current.wildcard_child = TrieNode()
                current = current.wildcard_child
            elif self._is_param_segment(segment):
                # Parameter segment
                param_name = self._extract_param_name(segment)
                if not current.param_child or current.param_child[0] != param_name:
                    current.param_child = (param_name, TrieNode())
                current = current.param_child[1]
            else:
                # Static segment
                if segment not in current.children:
                    current.children[segment] = TrieNode()
                current = current.children[segment]
        
        # Mark this node as an endpoint and store the contract
        current.is_endpoint = True
        current.contracts[method].append(contract)
        
        # Update statistics
        self._total_routes += 1
        if category == "static":
            self._static_routes += 1
        elif category == "parameterized":
            self._parameterized_routes += 1
        elif category == "wildcard":
            self._wildcard_routes += 1
    
    def register_many(self, contracts: List[ContractEntry]) -> None:
        """
        Register multiple contract entries at once.
        
        Args:
            contracts: List of ContractEntry objects to register
        """
        for contract in contracts:
            self.register(contract)
        
        logger.info(f"Registered {len(contracts)} routes: "
                   f"{self._static_routes} static, "
                   f"{self._parameterized_routes} parameterized, "
                   f"{self._wildcard_routes} wildcard")
    
    def _match_recursive(self, 
                        segments: List[str], 
                        index: int, 
                        node: TrieNode, 
                        method: HttpMethod,
                        path_params: Dict[str, str] = None) -> List[RouteMatch]:
        """
        Recursively match segments in the trie.
        
        Args:
            segments: List of path segments to match
            index: Current index in segments
            node: Current trie node
            method: HTTP method to match
            path_params: Collected path parameters so far
            
        Returns:
            List of matches found
        """
        # Initialize path_params if not provided
        if path_params is None:
            path_params = {}
        
        # If we've processed all segments, check if current node is an endpoint
        if index == len(segments):
            if node.is_endpoint and method in node.contracts:
                # Return matches for this endpoint
                return [
                    RouteMatch(
                        contract=contract,
                        path_params=path_params.copy(),
                        match_type="exact" if not path_params else "parameterized",
                        match_score=100 if not path_params else 50 + (10 * (len(segments) - len(path_params)))
                    )
                    for contract in node.contracts[method]
                ]
            return []
        
        # Current segment to match
        segment = segments[index]
        matches = []
        
        # Try static children (exact match)
        if segment in node.children:
            child_matches = self._match_recursive(
                segments, index + 1, node.children[segment], method, path_params.copy()
            )
            matches.extend(child_matches)
        
        # Try parameter children
        if node.param_child:
            param_name, param_node = node.param_child
            # Add this segment's value as a parameter
            new_params = path_params.copy()
            new_params[param_name] = segment
            
            param_matches = self._match_recursive(
                segments, index + 1, param_node, method, new_params
            )
            matches.extend(param_matches)
        
        # Try wildcard children (matches this and all remaining segments)
        if node.wildcard_child:
            # For wildcards, we consume all remaining segments
            wildcard_node = node.wildcard_child
            
            # If wildcard node is an endpoint with matching method
            if wildcard_node.is_endpoint and method in wildcard_node.contracts:
                # Add a match for each contract
                for contract in wildcard_node.contracts[method]:
                    matches.append(
                        RouteMatch(
                            contract=contract,
                            path_params=path_params.copy(),
                            match_type="wildcard",
                            match_score=10  # Wildcard matches are least specific
                        )
                    )
        
        return matches
    
    def match(self, method: Union[str, HttpMethod], path: str) -> Optional[RouteMatch]:
        """
        Find the best matching route for a given method and path.
        
        Args:
            method: HTTP method
            path: Request path
            
        Returns:
            RouteMatch if found, otherwise None
        """
        # Convert string method to HttpMethod enum if needed
        if isinstance(method, str):
            try:
                method = HttpMethod(method.upper())
            except ValueError:
                return None  # Invalid HTTP method
        
        # Split the path into segments
        segments = self._split_path(path)
        
        # Find all matches
        matches = self._match_recursive(segments, 0, self.root, method)
        
        if not matches:
            return None
        
        # Return the match with the highest score
        return max(matches, key=lambda m: m.match_score)
    
    def find_all_matches(self, method: Union[str, HttpMethod], path: str) -> List[RouteMatch]:
        """
        Find all matching routes for a given method and path.
        
        Args:
            method: HTTP method
            path: Request path
            
        Returns:
            List of RouteMatch objects sorted by score (highest first)
        """
        # Convert string method to HttpMethod enum if needed
        if isinstance(method, str):
            try:
                method = HttpMethod(method.upper())
            except ValueError:
                return []  # Invalid HTTP method
        
        # Split the path into segments
        segments = self._split_path(path)
        
        # Find all matches
        matches = self._match_recursive(segments, 0, self.root, method)
        
        # Sort by score (highest first)
        return sorted(matches, key=lambda m: m.match_score, reverse=True)
    
    def get_routes(self, method: Optional[HttpMethod] = None) -> List[ContractEntry]:
        """
        Get all registered routes, optionally filtered by method.
        
        Args:
            method: Optional HTTP method to filter by
            
        Returns:
            List of ContractEntry objects
        """
        routes = []
        
        def collect_routes(node: TrieNode):
            """Recursively collect routes from the trie."""
            if node.is_endpoint:
                if method:
                    # Filter by method if specified
                    if method in node.contracts:
                        routes.extend(node.contracts[method])
                else:
                    # Add all contracts for all methods
                    for method_contracts in node.contracts.values():
                        routes.extend(method_contracts)
            
            # Recurse to children
            for child in node.children.values():
                collect_routes(child)
            
            # Recurse to parameter child if exists
            if node.param_child:
                collect_routes(node.param_child[1])
            
            # Recurse to wildcard child if exists
            if node.wildcard_child:
                collect_routes(node.wildcard_child)
        
        # Start collection from the root
        collect_routes(self.root)
        return routes
    
    def clear(self) -> None:
        """Clear all registered routes."""
        self.root = TrieNode()
        self._total_routes = 0
        self._static_routes = 0
        self._parameterized_routes = 0
        self._wildcard_routes = 0


class RouteMatcherBenchmark:
    """Benchmark different route matching implementations."""
    
    @staticmethod
    def generate_test_data(num_routes: int = 500, num_requests: int = 1000, 
                          param_ratio: float = 0.3, wildcard_ratio: float = 0.1) -> Tuple[List[ContractEntry], List[Tuple[str, str]]]:
        """
        Generate test data for benchmarking.
        
        Args:
            num_routes: Number of routes to generate
            num_requests: Number of test requests to generate
            param_ratio: Ratio of routes with parameters
            wildcard_ratio: Ratio of routes with wildcards
            
        Returns:
            Tuple of (routes, test_requests)
        """
        import random
        
        # Common API paths
        base_paths = [
            "/api", "/v1", "/v2", "/users", "/products", "/orders",
            "/accounts", "/settings", "/auth", "/data", "/images"
        ]
        
        # Common path segments
        segments = [
            "create", "update", "delete", "get", "search", "filter",
            "info", "details", "stats", "history", "overview", "settings"
        ]
        
        # HTTP methods with weights
        methods = [
            (HttpMethod.GET, 0.5),     # 50% GET
            (HttpMethod.POST, 0.25),   # 25% POST
            (HttpMethod.PUT, 0.15),    # 15% PUT
            (HttpMethod.DELETE, 0.08), # 8% DELETE
            (HttpMethod.PATCH, 0.02)   # 2% PATCH
        ]
        
        # Generate routes
        routes = []
        created_paths = set()
        
        for _ in range(num_routes):
            # Choose HTTP method based on weights
            method = random.choices([m[0] for m in methods], 
                                  weights=[m[1] for m in methods])[0]
            
            # Generate path with 1-5 segments
            num_segments = random.randint(1, 5)
            
            # Start with a base path
            path_parts = [random.choice(base_paths)]
            
            # Add additional segments
            for i in range(1, num_segments):
                segment_type = random.random()
                
                if segment_type < param_ratio:
                    # Add parameter segment
                    param_name = random.choice([
                        "id", "userId", "productId", "orderId", 
                        "accountId", "itemId", "categoryId"
                    ])
                    path_parts.append(f"{{{param_name}}}")
                elif segment_type < param_ratio + wildcard_ratio:
                    # Add wildcard (only as the last segment)
                    if i == num_segments - 1:
                        path_parts.append("*")
                    else:
                        path_parts.append(random.choice(segments))
                else:
                    # Add static segment
                    path_parts.append(random.choice(segments))
            
            # Create the path
            path = "/" + "/".join(path_parts)
            
            # Ensure we don't duplicate paths for the same method
            if (method, path) in created_paths:
                continue
                
            created_paths.add((method, path))
            
            # Create the contract entry
            contract = ContractEntry(
                method=method,
                path=path,
                response_stub={"status_code": 200, "body": {}}
            )
            routes.append(contract)
        
        # Generate test requests (some matching the routes, some not)
        requests = []
        
        # Add requests that match existing routes (70%)
        for _ in range(int(num_requests * 0.7)):
            method, path = random.choice(list(created_paths))
            
            # For paths with parameters, fill in values
            if '{' in path:
                parts = path.split('/')
                for i, part in enumerate(parts):
                    if '{' in part and '}' in part:
                        # Replace {param} with a numeric ID
                        param_id = str(random.randint(1, 1000))
                        parts[i] = param_id
                path = '/'.join(parts)
            
            # For wildcard paths, add random segments
            if '*' in path:
                path = path.replace('*', '/'.join([
                    random.choice(segments) for _ in range(random.randint(0, 3))
                ]))
            
            requests.append((method.value, path))
        
        # Add requests that won't match (30%)
        for _ in range(num_requests - len(requests)):
            method = random.choices([m[0] for m in methods], 
                                  weights=[m[1] for m in methods])[0]
            
            # Generate a random path unlikely to match
            path = "/nonexistent/" + '/'.join([
                random.choice(segments) for _ in range(random.randint(1, 4))
            ])
            
            requests.append((method.value, path))
        
        # Shuffle the requests
        random.shuffle(requests)
        
        return routes, requests
    
    @staticmethod
    def benchmark(routes: List[ContractEntry], requests: List[Tuple[str, str]]) -> Dict[str, Any]:
        """
        Run benchmarks comparing regex-based and trie-based matchers.
        
        Args:
            routes: List of ContractEntry objects
            requests: List of (method, path) tuples to test
            
        Returns:
            Dictionary with benchmark results
        """
        # Create test registries
        trie_registry = TrieRouteRegistry()
        regex_registry = RouteRegistry()
        
        # Register routes
        start_time = time.time()
        trie_registry.register_many(routes)
        trie_register_time = time.time() - start_time
        
        start_time = time.time()
        regex_registry.register_many(routes)
        regex_register_time = time.time() - start_time
        
        # Test exact matches (existing routes)
        trie_matches = 0
        regex_matches = 0
        
        # Benchmark trie matcher
        start_time = time.time()
        for method, path in requests:
            match = trie_registry.match(method, path)
            if match:
                trie_matches += 1
        trie_match_time = time.time() - start_time
        
        # Benchmark regex matcher
        start_time = time.time()
        for method, path in requests:
            match = regex_registry.match(method, path)
            if match:
                regex_matches += 1
        regex_match_time = time.time() - start_time
        
        # Verify the matchers returned the same number of matches
        assert trie_matches == regex_matches, "Matchers returned different results"
        
        return {
            "routes": len(routes),
            "requests": len(requests),
            "matches": trie_matches,
            "trie_register_time": trie_register_time,
            "regex_register_time": regex_register_time,
            "trie_match_time": trie_match_time,
            "regex_match_time": regex_match_time,
            "trie_avg_match_ms": (trie_match_time / len(requests)) * 1000,
            "regex_avg_match_ms": (regex_match_time / len(requests)) * 1000,
            "speedup_factor": regex_match_time / trie_match_time if trie_match_time > 0 else float('inf')
        }


def run_benchmarks():
    """Run benchmarks with different dataset sizes and print results."""
    scenarios = [
        (100, 1000),   # Small API
        (500, 5000),   # Medium API
        (2000, 10000)  # Large API
    ]
    
    results = []
    
    for num_routes, num_requests in scenarios:
        print(f"Benchmarking with {num_routes} routes and {num_requests} requests...")
        routes, requests = RouteMatcherBenchmark.generate_test_data(
            num_routes=num_routes, 
            num_requests=num_requests
        )
        
        result = RouteMatcherBenchmark.benchmark(routes, requests)
        results.append(result)
        
        print(f"  Trie avg match time: {result['trie_avg_match_ms']:.3f} ms")
        print(f"  Regex avg match time: {result['regex_avg_match_ms']:.3f} ms")
        print(f"  Speedup factor: {result['speedup_factor']:.2f}x")
        print()
    
    print("Summary:")
    for i, result in enumerate(results):
        routes = result['routes']
        print(f"{routes} routes: Trie matcher is {result['speedup_factor']:.2f}x faster")