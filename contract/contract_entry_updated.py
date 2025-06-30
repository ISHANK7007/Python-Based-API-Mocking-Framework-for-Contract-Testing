import json
import re
from typing import Dict, Any, List, Optional, Union
from jinja2 import Environment, StrictUndefined


class ContextBuilder:
    """
    Builds template context with normalized request attributes
    for easy access in templates.
    """
    @staticmethod
    def build_template_context(request: Dict[str, Any]) -> Dict[str, Any]:
        method = request.get('method', '')
        path = request.get('path', '')
        path_params = request.get('path_params', {})
        query_params = request.get('query_params', {})
        headers = request.get('headers', {})
        body = request.get('body', {})

        # Normalize headers
        normalized_headers = {}
        for key, value in headers.items():
            normalized_headers[key] = value
            if isinstance(key, str):
                normalized_headers[key.lower()] = value

        # Parse body if it's a JSON string
        parsed_body = body
        if isinstance(body, str):
            try:
                parsed_body = json.loads(body)
            except json.JSONDecodeError:
                parsed_body = body

        return {
            "method": method,
            "path": path,
            "headers": normalized_headers,
            "query": query_params,
            "query_params": query_params,
            "path_params": path_params,
            "params": path_params,
            "body": parsed_body,
            "request": {
                "method": method,
                "path": path,
                "headers": normalized_headers,
                "query": query_params,
                "path_params": path_params,
                "body": parsed_body
            },
            "now": {
                "timestamp": f"{__import__('datetime').datetime.now().isoformat()}",
                "unix": f"{int(__import__('datetime').datetime.now().timestamp())}"
            },
            "uuid": f"{__import__('uuid').uuid4()}"
        }


class SafeTemplateEngine:
    """
    Jinja2 environment wrapper for safe templating
    """
    def __init__(self, strict_undefined=True, additional_filters=None, allowed_filters=None, allowed_tags=None):
        self.env = Environment(undefined=StrictUndefined if strict_undefined else None)
        if additional_filters:
            self.env.filters.update(additional_filters)
        # Filter enforcement can be added here if needed


class ConditionEvaluator:
    """
    Evaluates conditions like headers["X-Test"] == "foo" on request objects
    """
    def evaluate(self, condition: str, context: Dict[str, Any]) -> bool:
        try:
            return eval(condition, {"__builtins__": {}}, context)
        except Exception:
            return False


class ResponseResolver:
    """
    Resolves which response variant to use and renders it using templates.
    """
    def __init__(self, strict_undefined: bool = True):
        self.strict_undefined = strict_undefined
        self.template_engine = SafeTemplateEngine(
            strict_undefined=strict_undefined,
            additional_filters={
                'tojson': lambda obj: json.dumps(obj),
                'pretty_json': lambda obj: json.dumps(obj, indent=2),
                'join': lambda obj, sep=',': sep.join(obj) if isinstance(obj, list) else str(obj),
                'default': lambda obj, default='': obj if obj is not None else default,
                'coalesce': lambda *args: next((arg for arg in args if arg is not None), None)
            },
            allowed_filters={'tojson', 'pretty_json', 'default', 'join',
                             'lower', 'upper', 'title', 'trim', 'length',
                             'first', 'last', 'coalesce'},
            allowed_tags={'if', 'for', 'set'}
        )
        self.condition_evaluator = ConditionEvaluator()

    def build_request_context(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return ContextBuilder.build_template_context(request)

    def evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        return self.condition_evaluator.evaluate(condition, context)
