from enum import Enum
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator
import re

class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

class ResponseStub(BaseModel):
    status_code: int = Field(200, description="HTTP status code for the response")
    headers: Dict[str, str] = Field(default_factory=dict, description="Response headers")
    body: Optional[Union[Dict[str, Any], List[Any], str]] = Field(
        None, description="Response body content"
    )
    content_type: str = Field("application/json", description="Response content type")
    delay_ms: Optional[int] = Field(None, description="Optional delay in milliseconds")
    
    @validator('status_code')
    def validate_status_code(cls, v):
        if not 100 <= v <= 599:
            raise ValueError(f"Status code must be between 100 and 599, got {v}")
        return v

class PathParameter(BaseModel):
    name: str
    type: str = "string"
    required: bool = True
    description: Optional[str] = None
    example: Optional[Any] = None

class ContractEntry(BaseModel):
    id: Optional[str] = Field(None, description="Unique identifier for this mock entry")
    method: HttpMethod
    path: str = Field(..., description="URL path pattern, can include parameters like /users/{userId}")
    path_parameters: List[PathParameter] = Field(default_factory=list)
    query_parameters: Dict[str, PathParameter] = Field(default_factory=dict)
    request_headers: Dict[str, str] = Field(default_factory=dict, description="Required request headers")
    request_body_schema: Optional[Dict[str, Any]] = Field(
        None, description="JSON Schema for validating request body"
    )
    response_stub: ResponseStub
    description: Optional[str] = None
    
    @validator('path')
    def validate_path(cls, v):
        if not v.startswith('/'):
            raise ValueError("Path must start with /")
        
        # Check for valid parameter syntax in path (e.g., {userId})
        path_params = re.findall(r'{([^{}]+)}', v)
        for param in path_params:
            if not param.isidentifier():
                raise ValueError(f"Invalid path parameter name: {param}")
        
        return v
    
    @validator('path_parameters')
    def validate_path_parameters(cls, v, values):
        if 'path' not in values:
            return v
            
        # Extract parameter names from the path
        path_params_in_url = re.findall(r'{([^{}]+)}', values['path'])
        path_param_names = [param.name for param in v]
        
        # Ensure all path parameters are defined
        missing_params = set(path_params_in_url) - set(path_param_names)
        if missing_params:
            raise ValueError(f"Path parameters in URL not defined: {', '.join(missing_params)}")
        
        # Ensure no extra path parameters are defined
        extra_params = set(path_param_names) - set(path_params_in_url)
        if extra_params:
            raise ValueError(f"Defined path parameters not in URL: {', '.join(extra_params)}")
        
        return v