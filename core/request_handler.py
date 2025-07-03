import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contract.contract_entry import ContractEntry
from schema.strict_validator import StrictSchemaValidator  # Ensure proper import
from registry.route_registry import RouteRegistry


def handle_request(request, registry: RouteRegistry):
    """
    Handle an incoming API request.

    Args:
        request: The HTTP request object (with method, path, body, headers, query_params)
        registry: The RouteRegistry containing registered routes

    Returns:
        HTTP response object in dict format
    """
    # Match the route
    route_match = registry.match(request.method, request.path)

    if not route_match:
        return {
            "status_code": 404,
            "body": {
                "error": "Not Found",
                "message": f"No route found for {request.method} {request.path}"
            }
        }

    contract = route_match.contract

    # Parse the request body if present
    request_body = None
    if request.body:
        try:
            request_body = json.loads(request.body)
        except json.JSONDecodeError as e:
            return {
                "status_code": 400,
                "body": {
                    "error": {
                        "type": "invalid_json",
                        "message": f"Invalid JSON: {str(e)}",
                        "details": {
                            "line": e.lineno,
                            "column": e.colno,
                            "position": e.pos
                        }
                    }
                }
            }

    # Validate the request
    is_valid, error_response = StrictSchemaValidator.validate_request(
        contract,
        request_body=request_body,
        headers=request.headers,
        query_params=request.query_params,
        strict=True
    )

    if not is_valid:
        return error_response

    # Request is valid — generate stubbed response
    response_stub = contract.response_stub
    return {
        "status_code": response_stub.status_code or 200,
        "body": response_stub.body or {}
    }


def build_app(contracts: list[ContractEntry], use_trie: bool = False, strict_validation: bool = False) -> FastAPI:
    """
    Builds the FastAPI app with dynamically generated routes.
    """
    app = FastAPI(title="Mock API Server", version="1.0.0")
    registry = RouteRegistry()
    for contract in contracts:
        registry.register(contract, use_trie=use_trie)

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def catch_all(request: Request):
        body = await request.body()
        request_data = {
            "method": request.method,
            "path": request.url.path,
            "body": body.decode() if body else None,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params)
        }
        response_data = handle_request(request_data, registry)
        return JSONResponse(status_code=response_data["status_code"], content=response_data["body"])

    return app
