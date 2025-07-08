from core.chaos.chaos_seed_manager import ChaosSeedManager
from core.chaos_behavior_middleware import ChaosBehaviorMiddleware
from tests.utils.chaos_behavior_recorder import ChaosBehaviorRecorder
from tests.utils.mock_response_generator import MockResponseGenerator

def test_chaos_reproducibility():
    """Test that chaos behavior is reproducible with the same seed."""
    seed = 12345

    chaos_config = {
        'enabled': True,
        'seed': seed,
        'profiles': {
            'timeout_burst': {
                'enabled': True,
                'pattern': {
                    'type': 'sequence',
                    'sequence': [False, False, True]
                },
                'error_response': {
                    'status_code': 504,
                    'body': {'error': 'Gateway Timeout'}
                }
            }
        },
        'routes': {
            '/api/payments': {
                'POST': {
                    'use_profile': 'timeout_burst'
                }
            }
        }
    }

    # Simulate the full contract structure with chaos config
    CONTRACT = {
        "routes": {"/api/payments": {"POST": {}}},
        "chaos": chaos_config
    }

    # First run
    recorder1 = ChaosBehaviorRecorder()
    seed_manager1 = ChaosSeedManager(base_seed=seed)
    middleware1 = ChaosBehaviorMiddleware(
        chaos_config=chaos_config,
        seed_manager=seed_manager1,
        recorder=recorder1
    )
    generator1 = MockResponseGenerator(CONTRACT, middleware1)

    for i in range(10):
        generator1.get_response("/api/payments", "POST", {"id": f"req-{i}"})

    # Second run
    recorder2 = ChaosBehaviorRecorder()
    seed_manager2 = ChaosSeedManager(base_seed=seed)
    middleware2 = ChaosBehaviorMiddleware(
        chaos_config=chaos_config,
        seed_manager=seed_manager2,
        recorder=recorder2
    )
    generator2 = MockResponseGenerator(CONTRACT, middleware2)

    for i in range(10):
        generator2.get_response("/api/payments", "POST", {"id": f"req-{i}"})

    # Compare error logs
    assert len(recorder1.errors) == len(recorder2.errors), "Error count mismatch"
    assert len(recorder1.delays) == len(recorder2.delays), "Delay count mismatch"

    for i in range(len(recorder1.errors)):
        assert recorder1.errors[i]["response"] == recorder2.errors[i]["response"], f"Mismatch in error #{i}"
        assert recorder1.errors[i]["route"] == recorder2.errors[i]["route"]
        assert recorder1.errors[i]["method"] == recorder2.errors[i]["method"]

    for i in range(len(recorder1.delays)):
        assert recorder1.delays[i]["delay"] == recorder2.delays[i]["delay"], f"Mismatch in delay #{i}"
        assert recorder1.delays[i]["route"] == recorder2.delays[i]["route"]
        assert recorder1.delays[i]["method"] == recorder2.delays[i]["method"]
