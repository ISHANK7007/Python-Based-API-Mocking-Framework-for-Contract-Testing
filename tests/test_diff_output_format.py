import hashlib
import json
import os
import sys
import time
from typing import Dict, List, Any, Set, Optional, Tuple, Union, TypedDict, NamedTuple, FrozenSet, Callable
from functools import lru_cache
from dataclasses import dataclass, field, asdict
import click

from contract.contract_differ import EnhancedContractDiffer, ContractDiffer
from contract.contract_entry import ContractEntry
from contract.contract_loader import ContractLoader
from contract.contract_diff_formatter import EnhancedDiffFormatter
from core.diff_severity_grouping import SeverityGroupedFormatter
from core.diff_context_manager import SchemaDiff, ResponseDiff
from core.exceptions import Severity

from cli import cli

@dataclass
class RouteSignature:
    path: str
    method: str
    description: Optional[str] = None
    request_schema_hash: Optional[str] = None
    response_schema_hashes: FrozenSet[Tuple[str, str]] = field(default_factory=frozenset)

    @staticmethod
    def from_route(route) -> 'RouteSignature':
        request_schema_hash = None
        if route.request_schema:
            request_schema_hash = hash_json(route.request_schema)

        response_schema_hashes = set()
        for response in route.responses:
            status = str(response.status_code)
            response_hash = hash_json({
                'content_type': response.content_type,
                'headers': response.headers,
                'schema': response.schema,
                'body': response.body
            })
            response_schema_hashes.add((status, response_hash))

        return RouteSignature(
            path=route.path,
            method=route.method,
            description=route.description,
            request_schema_hash=request_schema_hash,
            response_schema_hashes=frozenset(response_schema_hashes)
        )

    def get_hash(self) -> str:
        return hash_json(asdict(self))

def hash_json(obj: Any) -> str:
    json_str = json.dumps(obj, sort_keys=True)
    return hashlib.md5(json_str.encode('utf-8')).hexdigest()

class OptimizedContractDiffer(EnhancedContractDiffer):
    def __init__(self):
        super().__init__()
        self._route_signatures_cache = {}
        self._schema_diff_cache = {}
        self._response_diff_cache = {}

    def diff_contracts(self, contract1: ContractEntry, contract2: ContractEntry) -> Dict[str, Any]:
        if len(self._route_signatures_cache) > 1000:
            self._route_signatures_cache.clear()
        if len(self._schema_diff_cache) > 1000:
            self._schema_diff_cache.clear()
        if len(self._response_diff_cache) > 1000:
            self._response_diff_cache.clear()

        signatures1 = self._get_route_signatures(contract1)
        signatures2 = self._get_route_signatures(contract2)

        if signatures1 == signatures2:
            return {'routes': {'added_routes': [], 'removed_routes': [], 'modified_routes': {}}, 'detailed_diffs': {}}

        route_diff = self._diff_routes_optimized(contract1, contract2, signatures1, signatures2)
        detailed_route_diffs = {}

        for path in route_diff['modified_routes']:
            route1 = next((r for r in contract1.routes if r.path == path), None)
            route2 = next((r for r in contract2.routes if r.path == path), None)
            if route1 and route2:
                sig1 = next((s for s in signatures1.values() if s.path == path), None)
                sig2 = next((s for s in signatures2.values() if s.path == path), None)

                schema_changed = sig1 and sig2 and sig1.request_schema_hash != sig2.request_schema_hash
                responses_changed = sig1 and sig2 and sig1.response_schema_hashes != sig2.response_schema_hashes

                schema_diff = None
                if schema_changed:
                    cache_key = (sig1.request_schema_hash, sig2.request_schema_hash)
                    if cache_key in self._schema_diff_cache:
                        schema_diff = self._schema_diff_cache[cache_key]
                    else:
                        schema_diff = self.diff_request_schema(route1, route2)
                        self._schema_diff_cache[cache_key] = schema_diff

                response_diff = None
                if responses_changed:
                    cache_key = (hash_json(sig1.response_schema_hashes), hash_json(sig2.response_schema_hashes))
                    if cache_key in self._response_diff_cache:
                        response_diff = self._response_diff_cache[cache_key]
                    else:
                        response_diff = self.diff_response_fields(route1, route2)
                        self._response_diff_cache[cache_key] = response_diff

                detailed_route_diffs[path] = {
                    'request_schema': schema_diff.__dict__ if schema_diff and schema_diff.is_different else None,
                    'responses': response_diff.__dict__ if response_diff and response_diff.is_different else None
                }

        result = {
            'routes': route_diff,
            'detailed_diffs': detailed_route_diffs
        }

        if contract1.metadata != contract2.metadata:
            result['metadata'] = {
                'from': contract1.metadata,
                'to': contract2.metadata,
                'changes': self._diff_dict(contract1.metadata, contract2.metadata)
            }

        return result

    def _get_route_signatures(self, contract: ContractEntry) -> Dict[str, RouteSignature]:
        contract_id = id(contract)
        if contract_id in self._route_signatures_cache:
            return self._route_signatures_cache[contract_id]

        signatures = {}
        for route in contract.routes:
            key = f"{route.path}:{route.method}"
            signatures[key] = RouteSignature.from_route(route)

        self._route_signatures_cache[contract_id] = signatures
        return signatures

    def _diff_routes_optimized(self, contract1: ContractEntry, contract2: ContractEntry,
                               signatures1: Dict[str, RouteSignature],
                               signatures2: Dict[str, RouteSignature]) -> Dict[str, Any]:
        keys1 = set(signatures1.keys())
        keys2 = set(signatures2.keys())

        added_routes = []
        for key in keys2 - keys1:
            sig = signatures2[key]
            route = next((r for r in contract2.routes if r.path == sig.path and r.method == sig.method), None)
            if route:
                added_routes.append({'path': route.path, 'method': route.method, 'description': route.description})

        removed_routes = []
        for key in keys1 - keys2:
            sig = signatures1[key]
            route = next((r for r in contract1.routes if r.path == sig.path and r.method == sig.method), None)
            if route:
                removed_routes.append({'path': route.path, 'method': route.method, 'description': route.description})

        modified_routes = {}
        for key in keys1 & keys2:
            sig1 = signatures1[key]
            sig2 = signatures2[key]
            if sig1.get_hash() == sig2.get_hash():
                continue

            changes = {}
            if sig1.description != sig2.description:
                changes['description'] = {'from': sig1.description, 'to': sig2.description}
            if sig1.request_schema_hash != sig2.request_schema_hash:
                changes['request_schema_changed'] = True
            if sig1.response_schema_hashes != sig2.response_schema_hashes:
                changes['responses_changed'] = True

            if changes:
                modified_routes[sig1.path] = changes

        return {'added_routes': added_routes, 'removed_routes': removed_routes, 'modified_routes': modified_routes}

    @lru_cache(maxsize=256)
    def diff_request_schema(self, route1, route2) -> SchemaDiff:
        return super().diff_request_schema(route1, route2)

    @lru_cache(maxsize=256)
    def diff_response_fields(self, route1, route2) -> ResponseDiff:
        return super().diff_response_fields(route1, route2)

def create_differ(optimize: bool = True) -> Union[ContractDiffer, OptimizedContractDiffer]:
    return OptimizedContractDiffer() if optimize else EnhancedContractDiffer()

class DiffPerformanceStats:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.route_count = 0
        self.unchanged_routes = 0
        self.changed_routes = 0
        self.cache_hits = 0
        self.schema_comparisons = 0

    def to_dict(self) -> Dict[str, Any]:
        duration = None
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
        return {
            'duration_ms': int(duration * 1000) if duration else None,
            'route_count': self.route_count,
            'unchanged_routes': self.unchanged_routes,
            'changed_routes': self.changed_routes,
            'cache_hits': self.cache_hits,
            'schema_comparisons': self.schema_comparisons,
            'unchanged_percentage': round((self.unchanged_routes / self.route_count) * 100, 2)
            if self.route_count > 0 else 0
        }

@cli.command()
@click.option('--from', 'from_file', required=True, help="Source contract file")
@click.option('--to', 'to_file', required=True, help="Target contract file to compare against")
@click.option('--format', 'output_format', default='text',
              type=click.Choice(['text', 'markdown', 'html', 'json']),
              help="Output format for the diff")
@click.option('--output', '-o', help="Output file path (defaults to stdout)")
@click.option('--details/--no-details', default=False, help="Show detailed information about each change")
@click.option('--optimize/--no-optimize', default=True, help="Use optimized diffing algorithm")
@click.option('--stats/--no-stats', default=False, help="Show performance statistics")
def diff(from_file, to_file, output_format, output, details, optimize, stats):
    if not os.path.exists(from_file):
        click.echo(f"Error: Source file '{from_file}' not found", err=True)
        sys.exit(1)
    if not os.path.exists(to_file):
        click.echo(f"Error: Target file '{to_file}' not found", err=True)
        sys.exit(1)

    try:
        loader = ContractLoader()
        differ = create_differ(optimize=optimize)
        perf_stats = DiffPerformanceStats() if stats else None

        if perf_stats:
            perf_stats.start_time = time.time()

        contract1 = loader.load(from_file)
        contract2 = loader.load(to_file)

        if perf_stats:
            perf_stats.route_count = len(contract1.routes) + len(contract2.routes)

        contract1_name = os.path.basename(from_file).split('.')[0]
        contract2_name = os.path.basename(to_file).split('.')[0]

        diff_result = differ.diff_contracts(contract1, contract2)

        formatter = EnhancedDiffFormatter()
        summaries = formatter.generate_change_summaries(diff_result)

        if perf_stats:
            perf_stats.end_time = time.time()
            perf_stats.changed_routes = (
                len(diff_result['routes']['added_routes']) +
                len(diff_result['routes']['removed_routes']) +
                len(diff_result['routes']['modified_routes'])
            )
            perf_stats.unchanged_routes = perf_stats.route_count - perf_stats.changed_routes
            if hasattr(differ, 'diff_request_schema') and hasattr(differ.diff_request_schema, 'cache_info'):
                perf_stats.cache_hits = differ.diff_request_schema.cache_info().hits
            perf_stats.schema_comparisons = len(diff_result.get('detailed_diffs', {}))

        if output_format == 'text':
            result = SeverityGroupedFormatter.format_as_text(summaries, details)
        elif output_format == 'markdown':
            result = formatter.format_as_markdown(summaries, "contract", contract1_name, contract2_name)
        elif output_format == 'html':
            result = formatter.format_as_html(summaries, "contract", contract1_name, contract2_name)
        elif output_format == 'json':
            result = formatter.format_as_json(summaries, "contract", contract1_name, contract2_name)
        else:
            click.echo(f"Error: Unsupported format: {output_format}", err=True)
            sys.exit(1)

        if stats and perf_stats:
            stats_text = "\n\nPERFORMANCE STATISTICS\n" + "-" * 50 + "\n"
            stats_dict = perf_stats.to_dict()
            stats_text += f"Duration: {stats_dict['duration_ms']} ms\n"
            stats_text += f"Routes analyzed: {stats_dict['route_count']}\n"
            stats_text += f"Unchanged routes: {stats_dict['unchanged_routes']} ({stats_dict['unchanged_percentage']}%)\n"
            stats_text += f"Changed routes: {stats_dict['changed_routes']}\n"
            stats_text += f"Cache hits: {stats_dict['cache_hits']}\n"
            stats_text += f"Schema comparisons: {stats_dict['schema_comparisons']}\n"
            result += stats_text

        if output:
            os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
            with open(output, 'w') as f:
                f.write(result)
            click.echo(f"Diff report written to {output}")
        else:
            click.echo(result)

        high_severity_changes = len([s for s in summaries
                                     if SeverityGroupedFormatter.map_change_to_severity(s) == Severity.HIGH])
        if high_severity_changes > 0:
            sys.exit(2)

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)
