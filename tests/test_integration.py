import threading
from typing import Tuple, Any, List

from contract.contract_entry import ContractEntry
from router.route_registry import RouteRegistry
from router.trie_matcher import TrieRouteRegistry
from schema.validator import StrictSchemaValidator

def create_server(
    contracts: List[ContractEntry],
    use_trie: bool = True,
    strict_validation: bool = True
) -> Tuple[Any, threading.Event]:
    """
    Create the mock API server application.
    """
    if use_trie:
        router = TrieRouteRegistry()
    else:
        router = RouteRegistry()

    router.register_many(contracts)

    shutdown_event = threading.Event()

    from flask import Flask, request, jsonify, make_response
    app = Flask(__name__)

    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({"status": "ok"})

    @app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    def handle_request(path):
        if not path.startswith('/'):
            path = '/' + path

        method = request.method
        route_match = router.match(method, path)

        if not route_match:
            return jsonify({
                "error": "Not Found",
                "message": f"No route found for {method} {path}"
            }), 404

        request_body = None
        if request.is_json and request.data:
            request_body = request.get_json()

        if strict_validation and route_match.contract.request_body_schema and request_body:
            is_valid, error_response = StrictSchemaValidator.validate_request(
                route_match.contract,
                request_body=request_body,
                headers=dict(request.headers),
                query_params=dict(request.args),
                strict=True
            )
            if not is_valid:
                return jsonify(error_response), error_response.get("status_code", 400)

        response_stub = route_match.contract.response_stub
        body = response_stub.body

        if isinstance(body, dict):
            import copy
            import datetime
            processed_body = copy.deepcopy(body)

            def process_dict_values(d, params):
                for key, value in d.items():
                    if isinstance(value, dict):
                        process_dict_values(value, params)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                process_dict_values(item, params)
                    elif isinstance(value, str):
                        for param_name, param_value in params.items():
                            d[key] = value.replace("{" + param_name + "}", param_value)

                        if "{request.body." in value and request_body:
                            for field, field_value in request_body.items():
                                placeholder = "{request.body." + field + "}"
                                if placeholder in value:
                                    d[key] = value.replace(placeholder, str(field_value))

                        if "{now}" in value:
                            now = datetime.datetime.now().isoformat()
                            d[key] = value.replace("{now}", now)

            process_dict_values(processed_body, route_match.path_params)

            response = make_response(jsonify(processed_body), response_stub.status_code)
            for header_name, header_value in response_stub.headers.items():
                response.headers[header_name] = header_value

            return response

        return jsonify(body), response_stub.status_code

    def shutdown_monitor():
        shutdown_event.wait()
        # Placeholder: Insert actual server shutdown logic

    shutdown_thread = threading.Thread(target=shutdown_monitor)
    shutdown_thread.daemon = True
    shutdown_thread.start()

    return app, shutdown_event
