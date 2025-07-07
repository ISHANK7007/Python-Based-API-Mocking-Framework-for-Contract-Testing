import time
import random

# === Mocked Chaos Middleware ===
class MockChaosMiddleware:
    def __init__(self, seed):
        random.seed(seed)

    def get_order_response(self, request_id):
        # Probabilistic error: 20% chance
        if random.random() < 0.2:
            return {"status_code": 500, "body": {"error": "Server Error"}}
        return {"status_code": 200, "body": {"message": "Order OK"}}

    def get_search_response(self):
        # Always delays by 3 seconds
        time.sleep(3)
        return {"status_code": 200, "body": {"message": "Search OK"}}

# === TC1: With seed 1234, 1 error out of 5 requests to /order ===
def test_order_error_reproducibility():
    chaos = MockChaosMiddleware(seed=1234)
    error_count = 0
    for i in range(5):
        response = chaos.get_order_response(f"req-{i}")
        if response["status_code"] == 500:
            error_count += 1
    print(f"🔁 TC1: Error responses out of 5 = {error_count}")
    assert error_count == 1

# === TC2: /search delays for at least 3 seconds ===
def test_search_delay():
    chaos = MockChaosMiddleware(seed=0)
    start = time.time()
    response = chaos.get_search_response()
    elapsed = (time.time() - start) * 1000
    print(f"⏱️ TC2: Delay = {int(elapsed)}ms")
    assert response["status_code"] == 200
    assert elapsed >= 2800

# === Run both tests ===
if __name__ == "__main__":
    test_order_error_reproducibility()
    test_search_delay()
    print("✅ All fallback chaos tests passed.")
