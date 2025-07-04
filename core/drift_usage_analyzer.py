import json
import re
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple, Counter as CounterType
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

@dataclass
class RouteUsageStats:
    """Usage statistics for a specific API route."""
    path: str
    method: str
    call_count: int
    unique_clients: int
    last_used: datetime
    avg_response_time: float
    status_counts: Dict[str, int]
    client_ip_list: Set[str]
    parameter_frequencies: Dict[str, Dict[str, int]]
    
    @property
    def success_rate(self) -> float:
        """Calculate the success rate for this route."""
        total = sum(self.status_counts.values())
        if total == 0:
            return 0.0
        successes = sum(self.status_counts.get(k, 0) for k in ('200', '201', '202', '204'))
        return round(successes / total * 100, 2)
    
    @property
    def error_rate(self) -> float:
        """Calculate the error rate for this route."""
        total = sum(self.status_counts.values())
        if total == 0:
            return 0.0
        errors = sum(self.status_counts.get(k, 0) for k in 
                    [str(code) for code in range(400, 600)])
        return round(errors / total * 100, 2)


class UsageDataProcessor:
    """
    Processes API session logs to extract usage patterns.
    """
    
    def __init__(self):
        self.route_stats = {}  # Maps route keys to RouteUsageStats
        self.time_series_data = defaultdict(lambda: defaultdict(int))  # Maps dates to {route_key: count}
        self.client_dependencies = defaultdict(set)  # Maps client IDs to sets of route keys
        self.route_dependencies = defaultdict(set)  # Maps route keys to other route keys often used together
        self.parameter_usage = defaultdict(lambda: defaultdict(Counter))  # Maps route_keys to {param_name: Counter of values}
    
    def load_session_logs(self, log_file_path: str, format: str = 'json'):
        """
        Load and process session logs from a file.
        
        Args:
            log_file_path: Path to the log file
            format: Log format (json, csv, etc.)
            
        Returns:
            Number of log entries processed
        """
        if format == 'json':
            return self._load_json_logs(log_file_path)
        elif format == 'csv':
            return self._load_csv_logs(log_file_path)
        else:
            raise ValueError(f"Unsupported log format: {format}")
    
    def _load_json_logs(self, log_file_path: str) -> int:
        """Load and process session logs in JSON format."""
        processed_count = 0
        
        with open(log_file_path, 'r') as f:
            log_data = json.load(f)
            
            # Handle both array of entries or object with entries array
            entries = log_data if isinstance(log_data, list) else log_data.get('entries', [])
            
            for entry in entries:
                self._process_log_entry(entry)
                processed_count += 1
        
        return processed_count
    
    def _load_csv_logs(self, log_file_path: str) -> int:
        """Load and process session logs in CSV format."""
        processed_count = 0
        
        with open(log_file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self._process_log_entry(row)
                processed_count += 1
        
        return processed_count
    
    def _process_log_entry(self, entry: Dict[str, Any]):
        """Process a single log entry."""
        # Extract common fields (adjust based on your log format)
        try:
            timestamp = self._parse_timestamp(entry.get('timestamp', entry.get('time')))
            method = entry.get('method', '').upper()
            path = entry.get('path', entry.get('url', ''))
            status_code = str(entry.get('status', entry.get('statusCode', 0)))
            client_ip = entry.get('clientIp', entry.get('ip', ''))
            client_id = entry.get('clientId', entry.get('client', ''))
            response_time = float(entry.get('responseTime', entry.get('duration', 0)))
            user_agent = entry.get('userAgent', '')
            
            # Handle URL patterns - convert to template format
            path = self._normalize_path(path)
            
            # Skip if we don't have the minimal required data
            if not (method and path):
                return
            
            # Create the route key
            route_key = f"{method}:{path}"
            
            # Update date-based statistics
            day_key = timestamp.strftime('%Y-%m-%d')
            self.time_series_data[day_key][route_key] += 1
            
            # Update or create the route stats
            if route_key not in self.route_stats:
                self.route_stats[route_key] = RouteUsageStats(
                    path=path,
                    method=method,
                    call_count=0,
                    unique_clients=0,
                    last_used=timestamp,
                    avg_response_time=0,
                    status_counts={},
                    client_ip_list=set(),
                    parameter_frequencies={}
                )
            
            stats = self.route_stats[route_key]
            
            # Update statistics
            stats.call_count += 1
            stats.last_used = max(stats.last_used, timestamp)
            
            # Update rolling average for response time
            stats.avg_response_time = (
                (stats.avg_response_time * (stats.call_count - 1) + response_time) / 
                stats.call_count
            )
            
            # Update status code counts
            stats.status_counts[status_code] = stats.status_counts.get(status_code, 0) + 1
            
            # Track client information
            if client_ip:
                stats.client_ip_list.add(client_ip)
            
            if client_id:
                self.client_dependencies[client_id].add(route_key)
            
            # Process query parameters if available
            query_params = entry.get('queryParameters', entry.get('query', {}))
            self._process_parameters(route_key, query_params)
            
            # Process request body parameters if available
            body_params = entry.get('requestBody', entry.get('body', {}))
            if isinstance(body_params, str):
                try:
                    body_params = json.loads(body_params)
                except json.JSONDecodeError:
                    body_params = {}
            
            self._process_parameters(route_key, body_params)
            
        except Exception as e:
            print(f"Error processing log entry: {e}")
    
    def _parse_timestamp(self, timestamp_str) -> datetime:
        """Parse a timestamp string into a datetime object."""
        if not timestamp_str:
            return datetime.now()
        
        # Try common formats
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',  # ISO format with milliseconds
            '%Y-%m-%dT%H:%M:%SZ',     # ISO format without milliseconds
            '%Y-%m-%d %H:%M:%S',      # Simple format
            '%Y/%m/%d %H:%M:%S',      # Alternative format
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue
        
        # Default to current time if we can't parse
        return datetime.now()
    
    def _normalize_path(self, path: str) -> str:
        """
        Convert concrete paths to template paths.
        
        E.g., /users/123 -> /users/{id}
        """
        # Common ID patterns
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
    
    def _process_parameters(self, route_key: str, params: Dict[str, Any], prefix: str = ''):
        """Process and record parameter usage patterns."""
        if not params or not isinstance(params, dict):
            return
            
        # Get the parameter frequencies dictionary for this route
        route_stats = self.route_stats[route_key]
        if 'parameter_frequencies' not in route_stats.__dict__:
            route_stats.parameter_frequencies = {}
        
        # Process each parameter
        for param_name, value in params.items():
            full_name = f"{prefix}{param_name}" if prefix else param_name
            
            if isinstance(value, dict):
                # Recursively process nested objects
                self._process_parameters(route_key, value, f"{full_name}.")
            elif isinstance(value, list):
                # For arrays, track length and sample first few values
                if full_name not in route_stats.parameter_frequencies:
                    route_stats.parameter_frequencies[full_name] = {
                        "values": Counter(),
                        "array_lengths": Counter()
                    }
                
                route_stats.parameter_frequencies[full_name]["array_lengths"][len(value)] += 1
                
                # Process a sample of array values (first 5)
                for i, item in enumerate(value[:5]):
                    if isinstance(item, (str, int, float, bool)):
                        route_stats.parameter_frequencies[full_name]["values"][str(item)] += 1
            else:
                # For simple values, just count occurrences
                if full_name not in route_stats.parameter_frequencies:
                    route_stats.parameter_frequencies[full_name] = {"values": Counter()}
                
                # Convert to string for counting
                str_value = str(value) if value is not None else "null"
                route_stats.parameter_frequencies[full_name]["values"][str_value] += 1
    
    def get_most_used_routes(self, limit: int = 10) -> List[Tuple[str, RouteUsageStats]]:
        """
        Get the most frequently used API routes.
        
        Args:
            limit: Maximum number of routes to return
            
        Returns:
            List of (route_key, stats) tuples ordered by call_count
        """
        return sorted(
            self.route_stats.items(),
            key=lambda x: x[1].call_count,
            reverse=True
        )[:limit]
    
    def get_route_usage(self, method: str, path: str) -> Optional[RouteUsageStats]:
        """
        Get usage statistics for a specific route.
        
        Args:
            method: HTTP method
            path: Route path
            
        Returns:
            RouteUsageStats object or None if not found
        """
        route_key = f"{method.upper()}:{path}"
        return self.route_stats.get(route_key)
    
    def get_route_usage_trend(self, route_key: str, days: int = 30) -> Dict[str, int]:
        """
        Get usage trend data for a route over time.
        
        Args:
            route_key: The route key (METHOD:path)
            days: Number of days to include
            
        Returns:
            Dictionary mapping dates to call counts
        """
        result = {}
        
        # Generate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        # Collect data for each date
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            result[date_str] = self.time_series_data.get(date_str, {}).get(route_key, 0)
            current_date += timedelta(days=1)
        
        return result
    
    def get_client_impact(self, route_keys: List[str]) -> Dict[str, Any]:
        """
        Analyze which clients would be affected by changes to the given routes.
        
        Args:
            route_keys: List of route keys affected by changes
            
        Returns:
            Dictionary with impact analysis
        """
        affected_clients = set()
        client_dependency_counts = Counter()
        
        # Find all clients that use these routes
        for client_id, routes in self.client_dependencies.items():
            client_impact = routes.intersection(route_keys)
            if client_impact:
                affected_clients.add(client_id)
                client_dependency_counts[client_id] = len(client_impact)
        
        # Calculate statistics
        total_clients = len(self.client_dependencies)
        affected_ratio = len(affected_clients) / total_clients if total_clients > 0 else 0
        
        return {
            "affected_clients_count": len(affected_clients),
            "affected_clients_ratio": affected_ratio,
            "total_clients": total_clients,
            "client_impact": [
                {"client_id": client_id, "affected_routes": count}
                for client_id, count in client_dependency_counts.most_common(10)
            ]
        }
    
    def export_usage_data(self, output_file: str) -> Dict[str, Any]:
        """
        Export usage data to a file for later import.
        
        Args:
            output_file: Path to output file
            
        Returns:
            Summary of exported data
        """
        export_data = {
            "generated_at": datetime.now().isoformat(),
            "route_stats": {},
            "time_series": dict(self.time_series_data),
            "metadata": {
                "total_routes": len(self.route_stats),
                "total_clients": len(self.client_dependencies),
                "date_range": {
                    "start": min(self.time_series_data.keys()) if self.time_series_data else None,
                    "end": max(self.time_series_data.keys()) if self.time_series_data else None
                }
            }
        }
        
        # Convert route stats for serialization
        for route_key, stats in self.route_stats.items():
            export_data["route_stats"][route_key] = {
                "path": stats.path,
                "method": stats.method,
                "call_count": stats.call_count,
                "unique_clients": len(stats.client_ip_list),
                "last_used": stats.last_used.isoformat(),
                "avg_response_time": stats.avg_response_time,
                "status_counts": stats.status_counts,
                "parameter_frequencies": stats.parameter_frequencies,
                "client_count": len(stats.client_ip_list)
            }
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return export_data["metadata"]