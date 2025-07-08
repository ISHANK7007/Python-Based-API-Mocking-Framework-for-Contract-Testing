class ChaosEventBucket:
    def __init__(self, time_window, endpoint):
        self.time_window = time_window  # e.g., "12-13h"
        self.endpoint = endpoint  # e.g., "/cart"
        self.chaos_events = {}  # type -> count, e.g., "timeout_burst" -> 3
        self.impact_metrics = {}  # e.g., "avg_response_time" -> 2500ms
        
class ChaosAggregate:
    def __init__(self):
        self.buckets = []  # List of ChaosEventBucket
        self.summary = {}  # High-level stats across all buckets