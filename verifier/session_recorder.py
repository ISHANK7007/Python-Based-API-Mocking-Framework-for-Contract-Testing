import os
import json
import uuid
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class SessionRecorder:
    def __init__(self, log_directory: str = "./session-logs", include_headers=True, include_body=True):
        self.log_directory = log_directory
        os.makedirs(log_directory, exist_ok=True)
        self.include_headers = include_headers
        self.include_body = include_body
        self.active_session = None
        self.buffer = []

    def start_recording(self, session_name: str = None):
        if self.active_session:
            return False
        session_id = session_name or f"session-{datetime.now().isoformat()}"
        self.active_session = {"id": session_id, "entries": []}
        return True

    def stop_recording(self):
        if not self.active_session:
            return None
        session = self.active_session
        self.active_session = None
        return session

    def save_session(self, session_id: str):
        if not session_id:
            raise ValueError("Missing session_id")
        path = os.path.join(self.log_directory, f"{session_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.active_session, f, indent=2)
        return path

    async def record_entry(self, request: Request, response_data: dict):
        if not self.active_session:
            return
        req_body = await request.json() if self.include_body else None
        entry = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": str(request.url.path),
            "headers": dict(request.headers) if self.include_headers else {},
            "body": req_body,
            "response": response_data,
        }
        self.active_session["entries"].append(entry)


def create_app():
    app = FastAPI()
    recorder = SessionRecorder()

    @app.post("/recorder/start")
    async def start_session(payload: dict):
        session_name = payload.get("sessionName")
        success = recorder.start_recording(session_name)
        return {"success": success, "message": "Recording started" if success else "Failed to start"}

    @app.post("/recorder/stop")
    async def stop_session():
        session = recorder.stop_recording()
        if not session:
            return JSONResponse(status_code=400, content={"success": False, "message": "No active session"})
        path = recorder.save_session(session["id"])
        return {
            "success": True,
            "message": "Recording saved",
            "sessionId": session["id"],
            "filePath": path,
        }

    @app.post("/api/products")
    async def create_order(request: Request):
        req_data = await request.json()
        response = {
            "products": [
                {"id": 1, "name": "Product 1", "price": 29.99},
                {"id": 2, "name": "Product 2", "price": 39.99},
            ]
        }
        await recorder.record_entry(request, response)
        return response

    @app.post("/api/orders")
    async def post_order(request: Request):
        req_data = await request.json()
        response = {
            "orderId": f"ORD-{uuid.uuid4()}",
            "status": "confirmed",
            "productId": req_data.get("productId"),
            "quantity": req_data.get("quantity"),
        }
        await recorder.record_entry(request, response)
        return response

    return app
