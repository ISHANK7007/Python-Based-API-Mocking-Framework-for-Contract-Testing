# core/server_factory.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from registry.route_registry import RouteRegistry
from core.request_handler import handle_request
from starlette.requests import Request
from starlette.responses import JSONResponse


def create_server(contracts, use_trie=True, strict_validation=False):
    """
    Creates and configures a FastAPI app from contract definitions.
    """
    app = FastAPI(title="Mock API Server")

    # Add basic CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize registry
    registry = RouteRegistry()
    for contract in contracts:
        registry.register(contract, use_trie=use_trie)

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def handle_all_routes(request: Request):
        """
        Catch-all route that handles any method/path and dispatches to our custom handler.
        """
        body = await request.body()
        response = handle_request(
            request={
                "method": request.method,
                "path": "/" + request.path_params["full_path"],
                "headers": dict(request.headers),
                "body": body.decode("utf-8") if body else None,
                "query_params": dict(request.query_params)
            },
            registry=registry
        )
        return JSONResponse(status_code=response["status_code"], content=response["body"])

    shutdown_event = None  # Placeholder
    return app, shutdown_event
