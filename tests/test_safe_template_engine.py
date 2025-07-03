
# ✅ FIXED safe_template_engine.py (includes SafeTemplateEngine, SafeTemplateEnvironment, ResponseResolver)
# Key fixes: json import, filter consistency, correct undefined config, modular registration

import re
import json
from typing import Any, Dict, List, Optional, Set
from jinja2 import Environment, Template, StrictUndefined, TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment
from jinja2.lexer import Token


class TemplateSecurityError(Exception):
    pass


class SafeTemplateEnvironment(SandboxedEnvironment):
    def __init__(self, 
                 allowed_filters: Optional[Set[str]] = None,
                 allowed_tags: Optional[Set[str]] = None, 
                 **kwargs):
        super().__init__(**kwargs)
        self._default_filters = {
            'default', 'lower', 'upper', 'title', 
            'trim', 'striptags', 'capitalize',
            'first', 'last', 'length', 'abs',
            'round', 'tojson', 'string', 'list',
            'replace', 'safe', 'urlencode', 
        }
        self._default_tags = {'if', 'for', 'set'}
        self.allowed_filters = self._default_filters.union(allowed_filters or set())
        self.allowed_tags = self._default_tags.union(allowed_tags or set())
        self.unsafe_patterns = [
            r'{{.*?\.__.*?}}',
            r'{%\s*import\s+.*?%}',
            r'{%\s*include\s+.*?%}',
            r'{%\s*macro\s+.*?%}',
            r'{%\s*call\s+.*?%}',
        ]

    def is_safe_template(self, source: str) -> bool:
        for pattern in self.unsafe_patterns:
            if re.search(pattern, source):
                return False
        try:
            tokens = self._lex_template(source)
            token_iter = iter(tokens)
            for token in token_iter:
                if token.type == 'block_begin':
                    tag_token = next(token_iter, None)
                    if tag_token and tag_token.value not in self.allowed_tags:
                        return False
                if token.type == 'pipe':
                    filter_token = next(token_iter, None)
                    if filter_token and filter_token.value not in self.allowed_filters:
                        return False
            return True
        except Exception:
            return False

    def _lex_template(self, source: str) -> List[Token]:
        return list(self.lexer.tokeniter(source))

    def from_string(self, source: str, **kwargs) -> Template:
        if not self.is_safe_template(source):
            raise TemplateSecurityError("Template contains potentially unsafe operations")
        return super().from_string(source, **kwargs)


class SafeTemplateEngine:
    def __init__(self, 
                 strict_undefined: bool = True,
                 additional_filters: Optional[Dict[str, Any]] = None,
                 allowed_filters: Optional[Set[str]] = None,
                 allowed_tags: Optional[Set[str]] = None):
        self.env = SafeTemplateEnvironment(
            undefined=StrictUndefined if strict_undefined else None,
            autoescape=True,
            allowed_filters=allowed_filters,
            allowed_tags=allowed_tags
        )
        self._register_default_filters()
        if additional_filters:
            for name, func in additional_filters.items():
                self.env.filters[name] = func

    def _register_default_filters(self):
        self.env.filters['tojson'] = lambda obj: json.dumps(obj)
        self.env.filters['string'] = lambda obj: str(obj) if obj is not None else ''
        self.env.filters['int'] = lambda obj: int(float(obj)) if obj is not None else 0
        self.env.filters['float'] = lambda obj: float(obj) if obj is not None else 0.0
        self.env.filters['bool'] = lambda obj: bool(obj)
        self.env.filters['list'] = lambda obj: list(obj) if obj is not None else []
        self.env.filters['dict'] = lambda obj: dict(obj) if obj is not None else {}

    def render_string(self, template_str: str, context: Dict[str, Any]) -> str:
        try:
            template = self.env.from_string(template_str)
            return template.render(**context)
        except TemplateSecurityError as e:
            raise TemplateSecurityError(f"Security error in template: {str(e)}")
        except TemplateSyntaxError as e:
            raise TemplateSyntaxError(f"Syntax error: {str(e)}", e.lineno, e.name, e.filename)
        except Exception as e:
            raise Exception(f"Render error: {str(e)}")

    def render_obj(self, obj: Any, context: Dict[str, Any]) -> Any:
        if isinstance(obj, str):
            return self.render_string(obj, context)
        elif isinstance(obj, dict):
            return {k: self.render_obj(v, context) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.render_obj(i, context) for i in obj]
        return obj


class ResponseResolver:
    def __init__(self, strict_undefined: bool = True):
        self.template_engine = SafeTemplateEngine(
            strict_undefined=strict_undefined,
            additional_filters={'tojson': lambda obj: json.dumps(obj)},
            allowed_filters={'tojson', 'default', 'lower', 'upper', 'title'},
            allowed_tags={'if', 'for'}
        )
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
        self._condition_pattern = re.compile(
            r'([a-zA-Z0-9_\.\[\]]+)\s*(==|!=|>|<|>=|<=|in|contains|matches)\s*(.+)'
        )

    def apply_templating(self, response: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        templated_response = {}
        if 'status' in response:
            templated_response['status'] = response['status']
        if 'headers' in response and response['headers']:
            templated_headers = {}
            for name, value in response['headers'].items():
                if isinstance(value, str):
                    try:
                        templated_headers[name] = self.template_engine.render_string(value, context)
                    except Exception as e:
                        print(f"Warning: Could not template header '{name}': {str(e)}")
                        templated_headers[name] = value
                else:
                    templated_headers[name] = value
            templated_response['headers'] = templated_headers
        if 'body' in response:
            try:
                templated_response['body'] = self.template_engine.render_obj(response['body'], context)
            except Exception as e:
                print(f"Warning: Could not template response body: {str(e)}")
                templated_response['body'] = response['body']
        return templated_response
