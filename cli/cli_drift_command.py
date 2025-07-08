import functools
import inspect
import logging
from typing import Optional, Dict, Any, Union, Callable

logger = logging.getLogger(__name__)

# Initialize contract enforcer global
_contract_enforcer = None

def validate_contract(version: str = 'latest', strict: bool = False, log_deprecated: bool = True):
    """
    Decorator for validating requests and responses against a contract version.
    """
    enforcer = _get_contract_enforcer()

    def decorator(func: Callable) -> Callable:
        signature = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = _extract_request(func, args, kwargs)
            if not request:
                logger.warning(f"Could not extract request from {func.__name__}")
                return func(*args, **kwargs)

            method = request.method.lower()
            path = _normalize_path(request.url_path)

            contract_version = enforcer.version_manager.get_version(version)
            if not contract_version:
                logger.warning(f"Contract version {version} not found")
                return func(*args, **kwargs)

            if contract_version.is_route_deprecated(method, path):
                deprecation_info = contract_version.get_deprecation_info(method, path)
                enforcer.usage_tracker.record_usage(
                    method, path, version, deprecation_info,
                    client_id=_get_client_id(request)
                )

                if log_deprecated:
                    logger.warning(
                        f"Deprecated route used: {method.upper()} {path} "
                        f"- Deprecated in: {deprecation_info.deprecated_in_version}, "
                        f"To be removed in: {deprecation_info.removal_in_version or 'N/A'}"
                    )

                if strict:
                    return _create_deprecation_error_response(request, deprecation_info)

            validate_request(request, method, path, contract_version)
            response = func(*args, **kwargs)
            validate_response(response, method, path, contract_version)

            if contract_version.is_route_deprecated(method, path):
                deprecation_info = contract_version.get_deprecation_info(method, path)
                response = _add_deprecation_headers(response, deprecation_info)

            return response

        return wrapper

    return decorator

def _get_contract_enforcer():
    """Get or initialize the global contract enforcer."""
    global _contract_enforcer

    if _contract_enforcer is None:
        # Replace these with actual imports from your project
        from contract.contract_version_manager import ContractVersionManager
        from verifier.contract_test_decorator import VersionAwareContractEnforcer

        version_manager = ContractVersionManager()
        _contract_enforcer = VersionAwareContractEnforcer(version_manager)

    return _contract_enforcer

def _extract_request(func, args, kwargs):
    """Extract request object based on web framework (Flask assumed)."""
    try:
        from flask import request as flask_request
        return flask_request
    except ImportError:
        return None

def _normalize_path(path):
    """Convert a concrete path to a route pattern."""
    return path

def _get_client_id(request):
    """Extract a client identifier from the request."""
    return request.headers.get('X-Client-ID')

def _create_deprecation_error_response(request, deprecation_info):
    """Create an error response when strict mode is active."""
    from flask import jsonify
    response = jsonify({
        "error": "deprecated_endpoint",
        "message": f"This endpoint is deprecated and will be removed in version {deprecation_info.removal_in_version}",
        "alternative": deprecation_info.alternative_route,
        "removal_date": deprecation_info.removal_date.isoformat() if deprecation_info.removal_date else None
    })
    response.status_code = 410
    return response

def _add_deprecation_headers(response, deprecation_info):
    """Add deprecation metadata to headers."""
    if hasattr(response, 'headers'):
        if deprecation_info.message:
            response.headers['Warning'] = f'299 - "{deprecation_info.message}"'
        else:
            response.headers['Warning'] = '299 - "This endpoint is deprecated"'

        if deprecation_info.removal_in_version:
            response.headers['X-Removal-Version'] = deprecation_info.removal_in_version
        if deprecation_info.alternative_route:
            response.headers['X-Alternative-Route'] = deprecation_info.alternative_route
        if deprecation_info.removal_date:
            response.headers['X-Removal-Date'] = deprecation_info.removal_date.isoformat()
    return response

def validate_request(request, method, path, contract_version):
    raise NotImplementedError("Request validation logic not implemented")

def validate_response(response, method, path, contract_version):
    raise NotImplementedError("Response validation logic not implemented")
