import functools
import inspect
import json
import os
from typing import Any, Callable, Dict, Optional, Type, Union
from pathlib import Path

# Reusing Pydantic for schema validation
from pydantic import BaseModel, ValidationError

# Simulation of the SnapshotVerifier class from our previous conversations
class SnapshotVerifier:
    def __init__(self, snapshot_dir: str = "snapshots"):
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(exist_ok=True, parents=True)
    
    def generate_snapshot_name(self, test_name: str, variant: str = "") -> str:
        """Generate a consistent snapshot filename based on test name."""
        safe_name = test_name.replace("/", "_").replace(":", "_")
        if variant:
            safe_name = f"{safe_name}_{variant}"
        return f"{safe_name}.snapshot.json"
    
    def save_snapshot(self, test_name: str, data: Any, variant: str = "") -> None:
        """Save data as a snapshot file."""
        snapshot_path = self.snapshot_dir / self.generate_snapshot_name(test_name, variant)
        with open(snapshot_path, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            
    def compare_with_snapshot(self, test_name: str, data: Any, 
                              variant: str = "", update_snapshot: bool = False) -> Dict[str, Any]:
        """
        Compare data with existing snapshot.
        Returns a dict with comparison results including any mismatches.
        """
        snapshot_path = self.snapshot_dir / self.generate_snapshot_name(test_name, variant)
        
        # Handle case when snapshot doesn't exist
        if not snapshot_path.exists():
            if update_snapshot:
                self.save_snapshot(test_name, data, variant)
                return {"status": "created", "mismatches": None}
            else:
                return {"status": "missing", "mismatches": "Snapshot does not exist"}
        
        # Load existing snapshot
        with open(snapshot_path, "r") as f:
            snapshot_data = json.load(f)
        
        # Apply smart tolerance for comparison
        mismatches = self._smart_compare(snapshot_data, data)
        
        if mismatches:
            if update_snapshot:
                self.save_snapshot(test_name, data, variant)
                return {"status": "updated", "mismatches": mismatches}
            return {"status": "failed", "mismatches": mismatches}
        else:
            return {"status": "passed", "mismatches": None}
    
    def _smart_compare(self, expected: Any, actual: Any, path: str = "$") -> Dict[str, Any]:
        """
        Smart comparison with tolerance for timestamps (±5s), UUID formats, 
        and array order differences.
        Returns dict of mismatches with path as keys.
        """
        # This is a simplified version - in reality, this would have more sophisticated
        # comparison logic for timestamps, UUIDs, etc.
        mismatches = {}
        
        if isinstance(expected, dict) and isinstance(actual, dict):
            # Compare dictionaries
            all_keys = set(expected.keys()) | set(actual.keys())
            for key in all_keys:
                if key not in expected:
                    mismatches[f"{path}.{key}"] = f"Key only in actual: {actual[key]}"
                elif key not in actual:
                    mismatches[f"{path}.{key}"] = f"Key only in expected: {expected[key]}"
                else:
                    nested_mismatches = self._smart_compare(
                        expected[key], actual[key], f"{path}.{key}"
                    )
                    mismatches.update(nested_mismatches)
        
        elif isinstance(expected, list) and isinstance(actual, list):
            # Compare lists - with intelligent handling for unordered arrays
            # Simplified here - real implementation would be more sophisticated
            if len(expected) != len(actual):
                mismatches[path] = f"Array length mismatch: expected {len(expected)}, got {len(actual)}"
            else:
                # Simple direct comparison for demonstration
                for i, (exp_item, act_item) in enumerate(zip(expected, actual)):
                    nested_mismatches = self._smart_compare(
                        exp_item, act_item, f"{path}[{i}]"
                    )
                    mismatches.update(nested_mismatches)
        
        elif expected != actual:
            # Direct value comparison with special handling for timestamps, UUIDs, etc.
            # Simplified here - would include tolerance checks in real implementation
            mismatches[path] = f"Value mismatch: expected {expected}, got {actual}"
        
        return mismatches


def validate_contract(
    request_model: Optional[Type[BaseModel]] = None,
    response_model: Optional[Type[BaseModel]] = None,
    snapshot_test: bool = False,
    update_snapshots: bool = False,
):
    """
    Decorator that validates request parameters and response against defined contract models
    and optionally against snapshots from previous test runs.
    
    Args:
        request_model: Pydantic model to validate the request against
        response_model: Pydantic model to validate the response against
        snapshot_test: Whether to validate against snapshots
        update_snapshots: Whether to update snapshots when mismatches are found
    """
    # Initialize the snapshot verifier if needed
    snapshot_verifier = SnapshotVerifier() if snapshot_test else None
    
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract test name for snapshot purposes
            test_name = f"{func.__module__}.{func.__qualname__}"
            
            # Validate request
            if request_model:
                # Extract parameters from the function call
                bound_args = inspect.signature(func).bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                try:
                    # Get request data excluding self/cls
                    request_data = {k: v for k, v in bound_args.arguments.items() 
                                 if k != 'self' and k != 'cls'}
                    
                    # Validate request against model
                    validated_request = request_model(**request_data)
                    
                    # Optionally check request against snapshot
                    if snapshot_test:
                        request_result = snapshot_verifier.compare_with_snapshot(
                            f"{test_name}.request", request_data, 
                            update_snapshot=update_snapshots
                        )
                        if request_result["status"] == "failed":
                            error_msg = "Request doesn't match snapshot:\n"
                            for path, mismatch in request_result["mismatches"].items():
                                error_msg += f"  - {path}: {mismatch}\n"
                            raise AssertionError(error_msg)
                            
                except ValidationError as e:
                    raise AssertionError(f"Request validation failed: {e}")
            
            # Execute the test function
            result = func(*args, **kwargs)
            
            # Validate response
            response_data = result
            if response_model and result is not None:
                try:
                    # Validate the response against the model
                    if isinstance(result, dict):
                        validated_response = response_model(**result)
                    else:
                        validated_response = response_model(result=result)
                except ValidationError as e:
                    raise AssertionError(f"Response validation failed: {e}")
            
            # Optionally verify response against snapshot
            if snapshot_test:
                response_result = snapshot_verifier.compare_with_snapshot(
                    f"{test_name}.response", response_data, 
                    update_snapshot=update_snapshots
                )
                if response_result["status"] == "failed":
                    error_msg = "Response doesn't match snapshot:\n"
                    for path, mismatch in response_result["mismatches"].items():
                        error_msg += f"  - {path}: {mismatch}\n"
                    raise AssertionError(error_msg)
            
            return result
        return wrapper
    return decorator