from typing import Dict

class UsageStats:
    def __init__(self, call_count, unique_clients, last_used, success_rate, avg_response_time, parameter_frequencies):
        self.call_count = call_count
        self.unique_clients = unique_clients
        self.last_used = last_used
        self.success_rate = success_rate
        self.avg_response_time = avg_response_time
        self.parameter_frequencies = parameter_frequencies

class UsageDataProcessor:
    def get_route_usage(self, method: str, path: str) -> UsageStats:
        raise NotImplementedError

    def get_client_impact(self, affected_routes: list) -> Dict:
        raise NotImplementedError
