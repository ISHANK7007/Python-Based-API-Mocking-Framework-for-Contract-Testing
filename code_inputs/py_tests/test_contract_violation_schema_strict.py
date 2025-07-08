import sys
import os
import threading
import time
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError, Extra
import uvicorn

# Ensure parent dir in path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Strict schema with no extra fields allowed
class UserInput(BaseModel, extra=Extra.forbid):
    name: str
    age: int

# Launch temporary mock server
def run_strict_mock_server():
    app = FastAPI()

    @app.post("/users")
    async def create_user(request: Request):
        try:
            body = await request.json()
            user = UserInput(**body)
            return JSONResponse(content={"status": "ok"}, status_code=200)
        except ValidationError as ve:
            return JSONResponse(content={"error": ve.errors()}, status_code=400)

    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")

# Run test against strict schema
def test_strict_violation_rejected():
    thread = threading.Thread(target=run_strict_mock_server, daemon=True)
    thread.start()
    time.sleep(2)  # Wait for server

    invalid_payload = {"name": "Alice", "age": 30, "extra": "not_allowed"}
    try:
        res = requests.post("http://localhost:8001/users", json=invalid_payload)
        assert res.status_code == 400
        print("✅ Test passed: Schema violation correctly rejected with 400")
        print("🔍 Error details:", res.json())
    except Exception as e:
        print("❌ Test failed:", e)

if __name__ == "__main__":
    test_strict_violation_rejected()
