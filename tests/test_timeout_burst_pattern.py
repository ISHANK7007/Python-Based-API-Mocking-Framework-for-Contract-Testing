import pytest
from core.chaos.state_store import InMemoryStateStore
from core.chaos_behavior_middleware import ChaosBehaviorMiddleware
from tests.utils.mock_response_generator import MockResponseGenerator
from tests.utils.chaos_behavior_recorder import ChaosBehaviorRecorder

def test_timeout_burst_pattern():
    """
    Verifies that the timeout_burst chaos profile (pattern-based) triggers
    every third request to return a 504 Gateway Timeout.
    """
    contract = {
        "routes": {"...": "..."},
        "chaos": {
            "global": {
                "enabled": True
            },
            "chaos_profiles": {
                "timeout_burst": {
                    "enabled": True,
                    "pattern": {
                        "type": "sequence",
                        "sequence": [False, False, True]
                    },
                    "error_response": {
                        "status_code": 504,
                        "body": {"error": "Gateway Timeout"}
                    }
                }
            },
            "routes": {
                "/api/payments": {
                    "POST": {
                        "use_profile": "timeout_burst"
                    }
                }
            }
        }
    }

    # Setup chaos environment
    recorder = ChaosBehaviorRecorder()
    state_store = InMemoryStateStore()
    chaos_middleware = ChaosBehaviorMiddleware(
        chaos_config=contract["chaos"],
        recorder=recorder,
        state_store=state_store
    )
    mock_generator = MockResponseGenerator(contract, chaos_middleware)

    # Run 10 requests and expect every 3rd to fail
    for i in range(10):
        response = mock_generator.get_response("/api/payments", "POST", {})

        if i % 3 == 2:
            assert response.get("status_code") == 504
            assert response.get("body", {}).get("error") == "Gateway Timeout"
        else:
            assert response.get("status_code") != 504

    # Ensure error count matches expectation
    assert len(recorder.errors) == 3

    # Reset and verify restart of pattern
    state_store.clear()

    for i in range(3):
        response = mock_generator.get_response("/api/payments", "POST", {})
        if i < 2:
            assert response.get("status_code") != 504
        else:
            assert response.get("status_code") == 504
