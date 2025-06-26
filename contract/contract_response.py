from pydantic import BaseModel
from typing import Dict, Any, Optional, List


class TemplatedResponse(BaseModel):
    status: int = 200
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None


class ContractResponse(BaseModel):
    status: int = 200
    headers: Optional[Dict[str, str]] = None
    body: Optional[Any] = None
    variants: Optional[List[Any]] = None
    fallback_response: Optional[TemplatedResponse] = None
