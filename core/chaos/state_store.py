class StateStore:
    """Interface for storing state across requests."""
    
    def get(self, key, default=None):
        """Get a value by key with optional default."""
        raise NotImplementedError
    
    def set(self, key, value):
        """Set a value by key."""
        raise NotImplementedError
    
    def clear(self):
        """Clear all state."""
        raise NotImplementedError
    
    def clear_with_prefix(self, prefix):
        """Clear all state with keys matching the prefix."""
        raise NotImplementedError

class InMemoryStateStore(StateStore):
    """In-memory implementation of state store."""
    
    def __init__(self):
        self.state = {}
    
    def get(self, key, default=None):
        return self.state.get(key, default)
    
    def set(self, key, value):
        self.state[key] = value
    
    def clear(self):
        self.state.clear()
    
    def clear_with_prefix(self, prefix):
        self.state = {k: v for k, v in self.state.items() if not k.startswith(prefix)}