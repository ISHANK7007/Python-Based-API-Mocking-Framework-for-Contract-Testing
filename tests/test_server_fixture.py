from functools import wraps
from pydantic import ValidationError
import pytest


def validate_contract(request_model=None, response_model=None, snapshot_test=False):
    """
    Decorator to validate request & response objects using Pydantic schemas.
    Optionally compares with snapshots.
    """

    def decorator(test_func):
        @wraps(test_func)
        def wrapper(*args, **kwargs):
            # Extract known fixtures from pytest context
            request_data = kwargs.get("request_data")
            snapshot_verifier = kwargs.get("snapshot_verifier", None)

            # Execute the test and capture the response
            response = test_func(*args, **kwargs)

            # --- Request Validation ---
            if request_model and request_data:
                try:
                    request_model(**request_data)
                except ValidationError as e:
                    pytest.fail(f"Request validation failed:\n{e}")

            # --- Response Validation ---
            if response_model:
                try:
                    response_model(**response)
                except ValidationError as e:
                    pytest.fail(f"Response validation failed:\n{e}")

            # --- Snapshot Validation ---
            if snapshot_test and snapshot_verifier:
                test_name = kwargs.get("request").node.nodeid.replace("::", ".")
                result = snapshot_verifier.compare_with_snapshot(
                    snapshot_name=test_name,
                    data=response
                )
                if result.get("status") == "failed":
                    pytest.fail(f"Snapshot mismatch:\n{result['mismatches']}")

            return response

        return wrapper

    return decorator
