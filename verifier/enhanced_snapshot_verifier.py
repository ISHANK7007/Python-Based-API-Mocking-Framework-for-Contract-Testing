import os
import json
import uuid
from datetime import datetime
from typing import Optional


class SessionRecorder:
    def __init__(self, log_directory: str = "./session-logs", include_headers=True, include_body=True):
        self.log_directory = log_directory
        os.makedirs(log_directory, exist_ok=True)
        self.include_headers = include_headers
        self.include_body = include_body
        self.active_session = None

    def start_recording(self, session_name: Optional[str] = None):
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

    async def record_entry(self, request, response_data: dict):
        if not self.active_session:
            return
        try:
            req_body = await request.json() if self.include_body else None
        except Exception:
            req_body = None
        entry = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": str(request.url.path),
            "headers": dict(request.headers) if self.include_headers else {},
            "body": req_body,
            "response": response_data,
        }
        self.active_session["entries"].append(entry)


class EnhancedSnapshotVerifier:
    def __init__(self, options=None):
        self.options = options or {
            "tolerances": {
                "timestampDriftSeconds": 5,
                "ignoreUUIDs": True,
                "sortArrays": True,
                "arrayFields": [],
                "timestampFields": ["created_at", "updated_at"],
                "uuidFields": ["orderId", "id"]
            }
        }

    def setStrict(self, strict: bool):
        if strict:
            self._originalTolerances = {**self.options["tolerances"]}
            self.options["tolerances"] = {
                "timestampDriftSeconds": 0,
                "ignoreUUIDs": False,
                "sortArrays": False,
                "arrayFields": [],
                "timestampFields": [],
                "uuidFields": []
            }
        elif hasattr(self, "_originalTolerances"):
            self.options["tolerances"] = self._originalTolerances
            del self._originalTolerances
        return self

    def verify(self, recorded: dict, expected: dict) -> bool:
        return self._compare(recorded, expected)

    def _compare(self, recorded, expected, path="") -> bool:
        if type(recorded) != type(expected):
            return False

        if isinstance(recorded, dict):
            for key in expected:
                if key not in recorded:
                    return False
                if not self._compare(recorded[key], expected[key], path + f".{key}"):
                    return False
            return True

        if isinstance(recorded, list):
            if self.options["tolerances"]["sortArrays"]:
                recorded = sorted(recorded)
                expected = sorted(expected)
            if len(recorded) != len(expected):
                return False
            for r_item, e_item in zip(recorded, expected):
                if not self._compare(r_item, e_item, path):
                    return False
            return True

        if isinstance(recorded, str):
            if any(f in path for f in self.options["tolerances"]["timestampFields"]):
                try:
                    r_time = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
                    e_time = datetime.fromisoformat(expected.replace("Z", "+00:00"))
                    delta = abs((r_time - e_time).total_seconds())
                    return delta <= self.options["tolerances"]["timestampDriftSeconds"]
                except Exception:
                    return recorded == expected
            if any(f in path for f in self.options["tolerances"]["uuidFields"]):
                if self.options["tolerances"]["ignoreUUIDs"]:
                    try:
                        uuid.UUID(recorded)
                        uuid.UUID(expected)
                        return True
                    except Exception:
                        return recorded == expected
        return recorded == expected
