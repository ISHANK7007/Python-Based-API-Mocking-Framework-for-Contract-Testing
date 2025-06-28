import re
import json
from typing import Any, Dict, List, Optional, Union
from jinja2 import Environment, Template, StrictUndefined
from pydantic import BaseModel


class ConditionEvaluationError(Exception):
    """Exception raised when there's an error evaluating a condition"""
    pass


class ResponseResolver:
    """
    Resolves which response variant to use based on conditions and applies
    template rendering with request context.
    """
    
    def __init__(self, strict_undefined: bool = True):
        """
        Initialize the response resolver
        
        Args:
            strict_undefined: If True, undefined variables in templates will raise an error
        """
        # Setup Jinja2 environment
        self.jinja_env = Environment(
            undefined=StrictUndefined if strict_undefined else None,
            autoescape=False,  # Don't auto-escape HTML since we're dealing with API responses
        )
        # Add custom filters
        self.jinja_env.filters['tojson'] = lambda obj: json.dumps(obj)
        
        # Compile regex patterns for condition parsing
        self._operators = {
            '==': lambda x, y: x == y,
            '!=': lambda x, y: x != y,
            '>': lambda x, y: x > y,
            '<': lambda x, y: x < y,
            '>=': lambda x, y: x >= y,
            '<=': lambda x, y: x <= y,
            'in': lambda x, y: x in y,
            'contains': lambda x, y: y in x,
            'matches': lambda x, y: bool(re.search(y, x)),
        }
        
        # Regex pattern to parse basic conditions
        self._condition_pattern = re.compile(
            r'([a-zA-Z0-9_\.\[\]]+)\s*(==|!=|>|<|>=|<=|in|contains|matches)\s*(.+)'
        )
    
    def build_request_context(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a context dictionary from the request for template rendering
        
        Args:
            request: The request object with method, path, headers, query, etc.
            
        Returns:
            Dictionary with request attributes for template context
        """
        # Normalize the request to ensure it has all expected sections
        context = {
            'method': request.get('method', ''),
            'path': request.get('path', ''),
            'path_params': request.get('path_params', {}),
            'query_params': request.get('query_params', {}),
            'headers': request.get('headers', {}),
            'body': request.get('body', {}),
        }
        
        # Add convenience aliases
        context['query'] = context['query_params']
        context['params'] = context['path_params']
        
        return context

    def evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition string against the request context
        
        Args:
            condition: Condition string (e.g., "headers.X-Env == 'test'")
            context: Request context dictionary
            
        Returns:
            Boolean result of the condition evaluation
            
        Raises:
            ConditionEvaluationError: If the condition cannot be parsed or evaluated
        """
        try:
            # Parse the condition
            match = self._condition_pattern.match(condition.strip())
            if not match:
                raise ConditionEvaluationError(f"Invalid condition format: {condition}")
                
            left_expr, operator, right_expr = match.groups()
            
            # Get the operator function
            op_func = self._operators.get(operator)
            if not op_func:
                raise ConditionEvaluationError(f"Unsupported operator: {operator}")
                
            # Get left operand value (property path)
            left_value = self._get_context_value(left_expr.strip(), context)

            # Parse right operand (value)
            right_value = self._parse_value(right_expr.strip())
                
            # Evaluate the condition
            return op_func(left_value, right_value)
        
        except Exception as e:
            if isinstance(e, ConditionEvaluationError):
                raise
            raise ConditionEvaluationError(f"Error evaluating condition '{condition}': {str(e)}")

    def _get_context_value(self, path: str, context: Dict[str, Any]) -> Any:
        """
        Get a value from context using dotted path notation
        
        Args:
            path: Dotted path to the value (e.g., "headers.X-Env")
            context: Context dictionary
            
        Returns:
            Value from context at the specified path
        """
        # Handle array access in path like headers['X-Env']
        array_pattern = re.compile(r'([a-zA-Z0-9_]+)\[[\'\"]([^\]]+)[\'\"]\]')
        path = array_pattern.sub(r'\1.\2', path)
        
        # Split the path and navigate through the dictionary
        parts = path.split('.')
        current = context
        
        for part in parts:
            if isinstance(current, dict):
                # Case insensitive lookup for headers
                if part == 'headers' and 'headers' in current:
                    current = {k.lower(): v for k, v in current['headers'].items()}
                else:
                    # Try lowercased key if exact key is not found
                    if part not in current and isinstance(part, str):
                        part_lower = part.lower()
                        if part_lower in current:
                            part = part_lower
                    
                    current = current.get(part)
            else:
                # Path longer than available nested objects
                return None
        
        return current

    def _parse_value(self, value_str: str) -> Any:
        """
        Parse a string value into an appropriate Python type
        
        Args:
            value_str: String representation of a value
            
        Returns:
            Parsed value (string, number, boolean, list, etc.)
        """
        value_str = value_str.strip()
        
        # String with quotes
        if (value_str.startswith("'") and value_str.endswith("'")) or \
           (value_str.startswith('"') and value_str.endswith('"')):
            return value_str[1:-1]
            
        # Boolean
        if value_str.lower() == 'true':
            return True
        if value_str.lower() == 'false':
            return False
            
        # Null/None
        if value_str.lower() == 'null' or value_str.lower() == 'none':
            return None
            
        # Number
        try:
            if '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            # Not a number, return as string
            return value_str

    def select_response_variant(self, 
                               variants: List[Dict[str, Any]], 
                               fallback_response: Optional[Dict[str, Any]], 
                               request_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Select the appropriate response variant based on conditions
        
        Args:
            variants: List of response variants with conditions
            fallback_response: Optional fallback response
            request_context: Request context for condition evaluation
            
        Returns:
            Selected response variant or fallback response
            
        Raises:
            ValueError: If no matching variant and no fallback response
        """
        if not variants:
            if fallback_response:
                return fallback_response
            raise ValueError("No response variants defined and no fallback response provided")
            
        # Evaluate each variant's condition
        for variant in variants:
            condition = variant.get('condition')
            if not condition:
                continue
                
            try:
                if self.evaluate_condition(condition, request_context):
                    return variant.get('response')
            except ConditionEvaluationError as e:
                # Log error but continue checking other variants
                print(f"Warning: {str(e)}")
        
        # If no matching variant, return fallback
        if fallback_response:
            return fallback_response
            
        # No match and no fallback
        raise ValueError("No matching response variant and no fallback response defined")

    def apply_templating(self, response: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Jinja2 templating to a response using the request context
        
        Args:
            response: Response data (status, headers, body)
            context: Request context for template rendering
            
        Returns:
            Templated response
        """
        templated_response = {}
        
        # Copy status code directly (not templated)
        if 'status' in response:
            templated_response['status'] = response['status']
        
        # Apply templating to headers
        if 'headers' in response and response['headers']:
            templated_headers = {}
            for name, value in response['headers'].items():
                if isinstance(value, str):
                    # Apply templating to string header values
                    template = self.jinja_env.from_string(value)
                    templated_value = template.render(**context)
                    templated_headers[name] = templated_value
                else:
                    templated_headers[name] = value
            templated_response['headers'] = templated_headers
        
        # Apply templating to body
        if 'body' in response:
            body = response['body']
            if isinstance(body, str):
                # String body - apply template directly
                template = self.jinja_env.from_string(body)
                templated_response['body'] = template.render(**context)
            elif isinstance(body, dict) or isinstance(body, list):
                # JSON body - convert to string, template, then parse back to object
                body_str = json.dumps(body)
                template = self.jinja_env.from_string(body_str)
                templated_json = template.render(**context)
                try:
                    templated_response['body'] = json.loads(templated_json)
                except json.JSONDecodeError:
                    # If template caused invalid JSON, keep as string
                    templated_response['body'] = templated_json
            else:
                # Non-string, non-JSON body (e.g., None) - pass through
                templated_response['body'] = body
        
        return templated_response

    def resolve_response(self, contract_entry: Any, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve the response for a contract entry based on request context
        
        Args:
            contract_entry: ContractEntry object with response configuration
            request: Request data
            
        Returns:
            Resolved and templated response
            
        Raises:
            ValueError: If no appropriate response can be resolved
        """
        # Build the request context for condition evaluation and templating
        request_context = self.build_request_context(request)
        
        # Get response configuration from contract entry
        response_config = contract_entry.response
        
        # If there are variants, select the appropriate one
        if response_config.variants:
            variants = [
                {
                    'condition': v.condition,
                    'response': v.response.dict()
                } for v in response_config.variants
            ]
            
            fallback = None
            if response_config.fallback_response:
                fallback = response_config.fallback_response.dict()
                
            # Try to resolve from variants
            try:
                selected_response = self.select_response_variant(
                    variants, fallback, request_context
                )
                return self.apply_templating(selected_response, request_context)
            except ValueError:
                # If variants exist but none match and no fallback,
                # fall back to basic response if defined
                pass
        
        # Basic response (no variants or no matching variant)
        basic_response = {
            'status': response_config.status,
            'headers': response_config.headers,
            'body': response_config.body
        }
        
        # Apply templating to the basic response
        return self.apply_templating(basic_response, request_context)