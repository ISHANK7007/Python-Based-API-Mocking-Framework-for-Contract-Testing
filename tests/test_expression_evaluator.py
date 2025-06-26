import re
import json
from typing import Any, Dict, List, Optional
from enum import Enum


class ConditionEvaluationError(Exception):
    """Exception raised when a condition cannot be evaluated"""
    pass


class TokenType(Enum):
    FIELD = "FIELD"
    OPERATOR = "OPERATOR"
    VALUE = "VALUE"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    OPEN_PAREN = "OPEN_PAREN"
    CLOSE_PAREN = "CLOSE_PAREN"
    ARRAY_ACCESS = "ARRAY_ACCESS"
    DOT = "DOT"


class SafeTemplateEngine:
    def __init__(self, strict_undefined: bool, additional_filters: Dict[str, Any], allowed_filters: set, allowed_tags: set):
        from jinja2 import Environment, StrictUndefined
        self.env = Environment(undefined=StrictUndefined if strict_undefined else None)
        self.env.filters.update(additional_filters)


class ConditionEvaluator:
    def __init__(self):
        self._operators = {
            '==': lambda x, y: x == y,
            '!=': lambda x, y: x != y,
            '>': lambda x, y: x > y,
            '<': lambda x, y: x < y,
            '>=': lambda x, y: x >= y,
            '<=': lambda x, y: x <= y,
            'in': lambda x, y: x in y,
            'contains': lambda x, y: y in x,
            'matches': lambda x, y: bool(re.match(str(y), str(x))),
            'exists': lambda x, _: x is not None,
            'empty': lambda x, _: not bool(x) if x is not None else True
        }
        self._token_patterns = [
            (r'([a-zA-Z0-9_.]+)\[[\'\"]([^\]]+)[\'\"]\]', TokenType.ARRAY_ACCESS),
            (r'\.', TokenType.DOT),
            (r'[a-zA-Z0-9_]+', TokenType.FIELD),
            (r'==|!=|>=|<=|>|<|in|contains|matches|exists|empty', TokenType.OPERATOR),
            (r'\bAND\b|\band\b|\&\&', TokenType.AND),
            (r'\bOR\b|\bor\b|\|\|', TokenType.OR),
            (r'\bNOT\b|\bnot\b|\!', TokenType.NOT),
            (r'\(', TokenType.OPEN_PAREN),
            (r'\)', TokenType.CLOSE_PAREN),
            (r'\'[^\']*\'|\"[^\"]*\"|\d+(\.\d+)?|true|false|null|undefined', TokenType.VALUE),
        ]

    def tokenize(self, condition: str) -> List:
        tokens, remaining = [], condition.strip()
        while remaining:
            remaining = remaining.lstrip()
            for pattern, token_type in self._token_patterns:
                match = re.match(pattern, remaining)
                if match:
                    if token_type == TokenType.ARRAY_ACCESS:
                        tokens.append((TokenType.FIELD, match.group(1)))
                        tokens.append((TokenType.ARRAY_ACCESS, match.group(2)))
                    else:
                        tokens.append((token_type, match.group(0)))
                    remaining = remaining[match.end():]
                    break
            else:
                raise ConditionEvaluationError(f"Syntax error in condition: '{remaining[:10]}...'")
        return tokens

    def _get_context_value(self, path_tokens, context: Dict[str, Any]):
        if path_tokens[0][0] != TokenType.FIELD:
            raise ConditionEvaluationError("Path must start with a field name")
        current = context
        for token_type, token_val in path_tokens:
            if token_type == TokenType.FIELD:
                if isinstance(current, dict):
                    current = current.get(token_val, current.get(token_val.lower(), None))
            elif token_type == TokenType.ARRAY_ACCESS:
                if isinstance(current, dict):
                    current = current.get(token_val, None)
                elif isinstance(current, list) and token_val.isdigit():
                    idx = int(token_val)
                    current = current[idx] if 0 <= idx < len(current) else None
        return current

    def _parse_value(self, val: str):
        if val.lower() in ('true', 'false'): return val.lower() == 'true'
        if val.lower() in ('null', 'none', 'undefined'): return None
        if val.isdigit(): return int(val)
        try: return float(val)
        except: return val.strip("'\"")

    def evaluate(self, condition: str, context: Dict[str, Any]) -> bool:
        tokens = self.tokenize(condition)
        ops = [i for i, t in enumerate(tokens) if t[0] == TokenType.OPERATOR]
        if not ops:
            raise ConditionEvaluationError("No operator found in condition")
        op_idx = ops[0]
        lhs = self._get_context_value(tokens[:op_idx], context)
        rhs = self._parse_value(tokens[op_idx+1][1]) if tokens[op_idx+1][0] == TokenType.VALUE else None
        op = tokens[op_idx][1]
        if op in self._operators:
            return self._operators[op](lhs, rhs)
        raise ConditionEvaluationError(f"Unsupported operator: {op}")


class ResponseResolver:
    def __init__(self, strict_undefined: bool = True):
        self.template_engine = SafeTemplateEngine(
            strict_undefined,
            additional_filters={'tojson': lambda o: json.dumps(o)},
            allowed_filters={'tojson', 'default', 'lower'},
            allowed_tags={'if', 'for'}
        )
        self.condition_evaluator = ConditionEvaluator()

    def evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        return self.condition_evaluator.evaluate(condition, context)

    def build_request_context(self, request: Dict[str, Any]) -> Dict[str, Any]:
        ctx = {
            'method': request.get('method', ''),
            'path': request.get('path', ''),
            'headers': request.get('headers', {}),
            'query': request.get('query_params', {}),
            'params': request.get('path_params', {}),
            'body': request.get('body', {})
        }
        return ctx

    def select_response_variant(self, variants, fallback, context):
        for v in variants:
            if 'condition' in v and self.evaluate_condition(v['condition'], context):
                return v['response']
        if fallback:
            return fallback
        raise ValueError("No matching variant and no fallback")

    def apply_templating(self, response: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        return response  # Placeholder for actual templating logic

    def resolve_response(self, contract_entry: Any, request: Dict[str, Any]) -> Dict[str, Any]:
        context = self.build_request_context(request)
        resp_cfg = contract_entry.response
        if resp_cfg.variants:
            variants = [{'condition': v.condition, 'response': v.response.dict()} for v in resp_cfg.variants]
            fallback = resp_cfg.fallback_response.dict() if resp_cfg.fallback_response else None
            selected = self.select_response_variant(variants, fallback, context)
            return self.apply_templating(selected, context)
        base = {'status': resp_cfg.status, 'headers': resp_cfg.headers, 'body': resp_cfg.body}
        return self.apply_templating(base, context)
