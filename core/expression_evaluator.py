from enum import Enum
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator, root_validator
import yaml
import os
import glob
from pathlib import Path
import uuid
import re


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class TemplatedResponse(BaseModel):
    status: int = 200
    headers: Dict[str, Any] = Field(default_factory=dict)
    body: Any = None


class ResponseVariant(BaseModel):
    condition: str
    response: TemplatedResponse


class ContractResponse(BaseModel):
    status: Optional[int] = 200
    headers: Dict[str, Any] = Field(default_factory=dict)
    body: Optional[Any] = None
    variants: Optional[List[ResponseVariant]] = None
    fallback_response: Optional[TemplatedResponse] = None


class Parameter(BaseModel):
    name: str
    schema: Dict[str, Any] = Field(default_factory=dict)
    required: bool = True


class ContractEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    method: HttpMethod
    path: str
    path_parameters: List[Parameter] = Field(default_factory=list)
    query_parameters: List[Parameter] = Field(default_factory=list)
    request_headers: Optional[Dict[str, Any]] = None
    request_body: Optional[Dict[str, Any]] = None
    response: ContractResponse

    @validator('path')
    def validate_path(cls, v):
        if not v.startswith('/'):
            raise ValueError("Path must start with '/'")
        return v

    @root_validator
    def validate_path_parameters(cls, values):
        path = values.get('path')
        path_params = values.get('path_parameters', [])
        
        # Extract parameter names from the path
        path_param_names = set(re.findall(r'\{([^}]+)\}', path))
        defined_param_names = {param.name for param in path_params}
        
        # Check if all path parameters are defined
        missing_params = path_param_names - defined_param_names
        if missing_params:
            raise ValueError(f"Path parameters {missing_params} referenced in path but not defined")
        
        # Check if all defined parameters are in the path
        extra_params = defined_param_names - path_param_names
        if extra_params:
            raise ValueError(f"Path parameters {extra_params} defined but not referenced in path")
        
        return values


class ContractLoadError(Exception):
    pass


class ContractConflictError(Exception):
    pass


class ContractLoader:
    def __init__(self):
        self.conflicts_detected = False
    
    def load_contracts(self, source, allow_duplicates=False):
        """
        Load contracts from a file, directory, or dictionary
        
        Args:
            source: File path, directory path, or dictionary with contract data
            allow_duplicates: Whether to allow duplicate routes (default: False)
            
        Returns:
            List of ContractEntry objects
        
        Raises:
            ContractLoadError: If there's an issue loading or parsing contracts
            ContractConflictError: If duplicate routes are found and allow_duplicates is False
        """
        if isinstance(source, dict):
            return self._load_from_dict(source, allow_duplicates)
        
        source_path = Path(source)
        if source_path.is_file():
            return self._load_from_file(source_path, allow_duplicates)
        elif source_path.is_dir():
            return self._load_from_directory(source_path, allow_duplicates)
        else:
            raise ContractLoadError(f"Source not found: {source}")
    
    def _load_from_file(self, file_path, allow_duplicates):
        """Load contracts from a single file"""
        try:
            with open(file_path, 'r') as file:
                content = yaml.safe_load(file)
                return self._load_from_dict(content, allow_duplicates)
        except yaml.YAMLError as e:
            raise ContractLoadError(f"Invalid YAML in {file_path}: {str(e)}")
        except Exception as e:
            raise ContractLoadError(f"Error loading contracts from {file_path}: {str(e)}")
    
    def _load_from_directory(self, dir_path, allow_duplicates):
        """Load contracts from all YAML files in a directory"""
        contracts = []
        for file_path in glob.glob(os.path.join(dir_path, "**/*.y*ml"), recursive=True):
            contracts.extend(self._load_from_file(file_path, allow_duplicates=True))
            
        if not allow_duplicates:
            self._check_for_duplicates(contracts)
            if self.conflicts_detected:
                raise ContractConflictError("Duplicate routes detected in contract directory")
                
        return contracts
    
    def _load_from_dict(self, data, allow_duplicates):
        """Parse contract data from a dictionary"""
        try:
            if not isinstance(data, list):
                if isinstance(data, dict) and 'contracts' in data:
                    data = data['contracts']
                else:
                    data = [data]  # Single contract case
            
            contracts = []
            for item in data:
                # Parse response section, including variants and fallback
                if 'response' in item:
                    response_data = item['response']
                    
                    # Create response object with proper structure
                    if isinstance(response_data, dict):
                        # Extract and validate variants if present
                        variants = None
                        fallback_response = None
                        
                        if 'variants' in response_data:
                            variants = response_data.pop('variants')
                        
                        if 'fallback_response' in response_data:
                            fallback_response = response_data.pop('fallback_response')
                        
                        # Create response with main data and variants
                        response = ContractResponse(
                            **response_data,
                            variants=[ResponseVariant(**v) for v in variants] if variants else None,
                            fallback_response=TemplatedResponse(**fallback_response) if fallback_response else None
                        )
                    else:
                        response = ContractResponse(body=response_data)
                    
                    item['response'] = response
                
                contract = ContractEntry(**item)
                contracts.append(contract)
            
            if not allow_duplicates:
                self._check_for_duplicates(contracts)
                if self.conflicts_detected:
                    raise ContractConflictError("Duplicate routes detected in contract data")
                    
            return contracts
        except Exception as e:
            raise ContractLoadError(f"Error parsing contract data: {str(e)}")
    
    def _check_for_duplicates(self, contracts):
        """Check for duplicate routes in contract list"""
        route_map = {}
        self.conflicts_detected = False
        
        for contract in contracts:
            route_key = f"{contract.method.value}:{contract.path}"
            if route_key in route_map:
                self.conflicts_detected = True
                # We could break here, but continuing gives more complete error information
            route_map[route_key] = True