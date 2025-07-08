class UsageDriftCorrelator:
    def __init__(self, session_recorder, contract_analyzer):
        self.session_recorder = session_recorder
        self.contract_analyzer = contract_analyzer
        
    def correlate_by_timeframe(self, start_date, end_date):
        # Get contract changes in timeframe
        contract_changes = self.contract_analyzer.get_changes_in_period(start_date, end_date)
        
        # Get usage logs in same timeframe
        usage_logs = self.session_recorder.get_sessions_in_period(start_date, end_date)
        
        # Map usage to contract versions
        return self._map_usage_to_contracts(usage_logs, contract_changes)
    
    def analyze_endpoint_evolution(self, endpoint_path):
        # Track how a specific endpoint's usage changed as its schema evolved
        endpoint_changes = self.contract_analyzer.get_endpoint_history(endpoint_path)
        endpoint_usage = self.session_recorder.get_endpoint_usage(endpoint_path)
        
        return self._correlate_changes_with_usage(endpoint_changes, endpoint_usage)