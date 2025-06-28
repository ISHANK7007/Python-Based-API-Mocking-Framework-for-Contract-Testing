import time
import re
import json
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from functools import lru_cache
from pydantic import BaseModel

from fastapi import APIRouter
from core.safe_template_engine import SafeTemplateEngine
from core.exceptions import ConditionEvaluationError, ContractLoadError
from core.tokenizer import TokenType
from core.server import server
from contract.contract_entry import ContractEntry
from contract.contract_response import ContractResponse, TemplatedResponse

app = APIRouter()


class CompiledCondition:
    def __init__(self, condition_str: str, evaluator: 'ConditionEvaluator'):
        self.original_condition = condition_str
        self.tokens = evaluator.tokenize(condition_str)
        self.required_paths = self._extract_paths()
        self.predicate = self._compile_predicate(evaluator)

    def _extract_paths(self) -> List[str]:
        paths = []
        current_path = []
        for token_type, token_value in self.tokens:
            if token_type == TokenType.FIELD:
                current_path.append(token_value)
            elif token_type == TokenType.ARRAY_ACCESS:
                current_path.append(f"['{token_value}']")
            elif token_type == TokenType.DOT:
                continue
            else:
                if current_path:
                    path_str = ''.join(current_path)
                    current_path = []
                    if path_str and path_str not in paths:
                        paths.append(path_str)
        if current_path:
            path_str = ''.join(current_path)
            if path_str and path_str not in paths:
                paths.append(path_str)
        return paths

    def _compile_predicate(self, evaluator: 'ConditionEvaluator') -> Callable[[Dict[str, Any]], bool]:
        operator_positions = [i for i, (t, _) in enumerate(self.tokens) if t == TokenType.OPERATOR]
        if not operator_positions:
            return lambda _: False
        op_position = operator_positions[0]
        left_tokens = self.tokens[:op_position]
        operator_type, operator_value = self.tokens[op_position]
        right_tokens = self.tokens[op_position + 1:]
        op_func = evaluator._operators.get(operator_value)
        if not op_func:
            return lambda _: False
        if operator_value in ('exists', 'empty'):
            def predicate(context: Dict[str, Any]) -> bool:
                left_value = evaluator._get_context_value(left_tokens, context)
                return op_func(left_value, None)
            return predicate
        if right_tokens and right_tokens[0][0] == TokenType.VALUE:
            right_value = evaluator._parse_value(right_tokens[0][1])
            def predicate(context: Dict[str, Any]) -> bool:
                left_value = evaluator._get_context_value(left_tokens, context)
                return op_func(left_value, right_value)
        else:
            def predicate(context: Dict[str, Any]) -> bool:
                left_value = evaluator._get_context_value(left_tokens, context)
                right_value = evaluator._get_context_value(right_tokens, context)
                return op_func(left_value, right_value)
        return predicate

    def evaluate(self, context: Dict[str, Any]) -> bool:
        try:
            return self.predicate(context)
        except Exception:
            return False

    def __str__(self) -> str:
        return f"CompiledCondition({self.original_condition})"


class ConditionEvaluator:
    def __init__(self):
        self._operators = {
            '==': lambda x, y: x == y,
            'eq': lambda x, y: x == y,
            '!=': lambda x, y: x != y,
            'ne': lambda x, y: x != y,
            '>': lambda x, y: x > y,
            'gt': lambda x, y: x > y,
            '<': lambda x, y: x < y,
            'lt': lambda x, y: x < y,
            '>=': lambda x, y: x >= y,
            'ge': lambda x, y: x >= y,
            '<=': lambda x, y: x <= y,
            'le': lambda x, y: x <= y,
            'in': lambda x, y: x in y,
            'contains': lambda x, y: y in x,
            'matches': lambda x, y: bool(re.match(str(y), str(x))),
            'exists': lambda x, _: x is not None,
            'empty': lambda x, _: not bool(x) if x is not None else True,
        }
        self._condition_cache = {}

    def compile_condition(self, condition: str) -> CompiledCondition:
        if not condition or not condition.strip():
            raise ConditionEvaluationError("Empty condition")
        condition = condition.strip()
        if condition in self._condition_cache:
            return self._condition_cache[condition]
        try:
            compiled = CompiledCondition(condition, self)
            self._condition_cache[condition] = compiled
            return compiled
        except Exception as e:
            raise ConditionEvaluationError(f"Error compiling condition '{condition}': {str(e)}")

    @lru_cache(maxsize=128)
    def evaluate_cached(self, condition: str, context_hash: str) -> bool:
        compiled = self.compile_condition(condition)
        return compiled.evaluate(json.loads(context_hash))


class ResponseVariant(BaseModel):
    condition: str
    response: Any
    compiled_condition: Optional[CompiledCondition] = None


@app.get("/mockapi/performance")
async def performance_metrics():
    resolver_metrics = server.response_resolver.get_performance_metrics()
    total_time_ms = resolver_metrics["total_condition_time_ms"] + resolver_metrics["total_template_time_ms"]
    condition_pct = 0
    template_pct = 0
    if total_time_ms > 0:
        condition_pct = round((resolver_metrics["total_condition_time_ms"] / total_time_ms) * 100, 1)
        template_pct = round((resolver_metrics["total_template_time_ms"] / total_time_ms) * 100, 1)
    metrics = {
        **resolver_metrics,
        "condition_time_pct": condition_pct,
        "template_time_pct": template_pct,
        "total_processing_time_ms": total_time_ms,
        "optimization_impact": {
            "compiled_conditions_used": len(server.response_resolver.condition_evaluator._condition_cache),
            "estimated_parsing_time_saved_ms": round(
                len(server.response_resolver.condition_evaluator._condition_cache) *
                resolver_metrics["avg_condition_time_ms"] * 0.7, 2
            )
        }
    }
    return metrics
