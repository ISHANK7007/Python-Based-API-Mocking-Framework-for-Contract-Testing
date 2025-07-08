class ChaosBehaviorRecorder:
    def __init__(self):
        self.errors = []
        self.delays = []

    def record_error(self, error_response, route, method):
        self.errors.append({
            "route": route,
            "method": method,
            "response": error_response
        })

    def record_delay(self, delay_ms, route, method):
        self.delays.append({
            "route": route,
            "method": method,
            "delay": delay_ms
        })
