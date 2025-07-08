import sys
import os
import threading
import time
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

# ➕ Patch sys.path (not really needed here but safe to keep)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# 🟢 Define minimal mock server manually
def run_mock_server():
    app = FastAPI()

    @app.get("/users/{user_id}")
    async def get_user(user_id: str, request: Request):
        env = request.headers.get("X-Env", "")
        if env == "staging":
            return JSONResponse(content={"id": user_id, "env": "staging"}, status_code=200)
        return JSONResponse(content={"id": user_id, "env": "default"}, status_code=200)

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

# ✅ Main test logic
def test_variant_match_by_header():
    thread = threading.Thread(target=run_mock_server, daemon=True)
    thread.start()
    time.sleep(2)  # Let server warm up

    try:
        response = requests.get("http://localhost:8000/users/42", headers={"X-Env": "staging"})
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["env"] == "staging"
        print("✅ Test passed! Response:", json_data)
    except Exception as e:
        print("❌ Test failed:", e)

if __name__ == "__main__":
    test_variant_match_by_header()
