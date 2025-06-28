import argparse
import logging
import sys
from typing import Dict, Any, List, Optional, Union, Set, Tuple
import json
import colorama
from colorama import Fore, Style

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import time

from contract.contract_loader import ContractLoader
from contract.contract_entry import ContractEntry
from router.trie_matcher import TrieRouteRegistry
from router.route_registry import RouteRegistry
from core.response_resolver import ResponseResolver
from core.debug_logger import DebugLogger

colorama.init()

class MockServer:
    def __init__(self, 
                 contracts: List[ContractEntry],
                 strict_validation: bool = False,
                 use_trie: bool = True,
                 debug_matching: bool = False):
        self.contracts = contracts
        self.strict_validation = strict_validation
        self.debug_matching = debug_matching

        self.registry = TrieRouteRegistry() if use_trie else RouteRegistry()
        for contract in contracts:
            self.registry.register(contract)

        self.debug_logger = DebugLogger(enabled=debug_matching, level="DEBUG" if debug_matching else "INFO")

        self.response_resolver = ResponseResolver(
            strict_undefined=strict_validation,
            debug_logger=self.debug_logger
        )

        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        app = FastAPI(title="Mock API Server")

        @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
        async def handle_request(request: Request, full_path: str):
            start_time = time.time()
            path = f"/{full_path}" if not full_path.startswith("/") else full_path
            method = request.method

            request_id = self.debug_logger.request_start(method, path)
            match_result = self.registry.match(method, path)

            if not match_result:
                self.debug_logger.request_complete(request_id, 404, (time.time() - start_time) * 1000)
                return JSONResponse(status_code=404, content={"error": f"No mock defined for {method} {path}"})

            contract_entry, path_params = match_result.contract, match_result.params
            self.debug_logger.route_match(request_id, contract_entry.path, path_params)

            request_data = await self._build_request_data(request, path_params)

            if self.strict_validation:
                pass

            try:
                resolved_response = self.response_resolver.resolve_response(contract_entry, request_data, request_id)
                status = resolved_response.get("status", 200)
                headers = resolved_response.get("headers", {})
                body = resolved_response.get("body")

                content = body
                if isinstance(body, (dict, list)):
                    content = json.dumps(body)
                    if "content-type" not in {k.lower(): v for k, v in headers.items()}:
                        headers["Content-Type"] = "application/json"

                self.debug_logger.request_complete(request_id, status, (time.time() - start_time) * 1000)
                return Response(content=content, status_code=status, headers=headers)

            except Exception as e:
                self.debug_logger.request_complete(request_id, 500, (time.time() - start_time) * 1000)
                return JSONResponse(status_code=500, content={"error": "Error resolving mock response", "message": str(e)})

        return app

    async def _build_request_data(self, request: Request, path_params: Dict[str, str]) -> Dict[str, Any]:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass

        return {
            "method": request.method,
            "path": str(request.url.path),
            "headers": dict(request.headers),
            "query": dict(request.query_params),
            "body": body,
            "params": path_params,
        }

def create_cli_parser():
    parser = argparse.ArgumentParser(description="Mock API Server for testing and development")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    serve_parser = subparsers.add_parser("serve", help="Start the mock API server")
    serve_parser.add_argument("-c", "--contract", required=True, help="Path to contract file or directory")
    serve_parser.add_argument("-p", "--port", type=int, default=8000, help="Server port (default: 8000)")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Server host (default: 127.0.0.1)")
    serve_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    serve_parser.add_argument("--reload", action="store_true", help="Reload server on code changes (development)")
    serve_parser.add_argument("--strict-validation", action="store_true", help="Enable strict request validation")
    serve_parser.add_argument("--use-trie", action="store_true", default=True, help="Use Trie-based route matching")
    serve_parser.add_argument("--debug-matching", action="store_true", help="Enable detailed condition matching logs")

    return parser

def main():
    parser = create_cli_parser()
    args = parser.parse_args()

    if args.command == "serve":
        try:
            loader = ContractLoader()
            contracts = loader.load_contracts(args.contract)

            print(f"{Fore.GREEN}Starting Mock API Server with {len(contracts)} routes")
            if args.debug_matching:
                print(f"{Fore.YELLOW}Debug matching enabled - detailed condition logs will be shown")
            print(f"Server running at http://{args.host}:{args.port}{Style.RESET_ALL}")

            server = MockServer(
                contracts=contracts,
                strict_validation=args.strict_validation,
                use_trie=args.use_trie,
                debug_matching=args.debug_matching
            )

            import uvicorn
            uvicorn.run(
                server.app,
                host=args.host,
                port=args.port,
                log_level="info" if args.verbose else "warning",
                reload=args.reload
            )

        except Exception as e:
            print(f"{Fore.RED}Error starting server: {str(e)}{Style.RESET_ALL}")
            sys.exit(1)

if __name__ == "__main__":
    main()