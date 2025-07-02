
import json
import random
from typing import Dict, List, Any, Set, Optional, Tuple, Union, Generator
from jsonschema import Draft7Validator
from schema.validator import SchemaValidator
from contract.contract_loader import ContractLoader
from contract.contract_response import ContractResponse

from contract.contract_differ import ContractDiffer


from contract.contract_diff_types import SchemaDiff, ResponseDiff, ChangeType, ChangeSummary
from contract.contract_diff_formatter import DiffFormatter
from contract.contract_change_flagger import BreakingChangeClassifier

from contract.contract_version_manager import ContractVersionManager

from contract.contract_version_manager import ContractVersionManager
from contract.contract_entry import Route

class SchemaCompatibilityValidator:
    """
    Validates compatibility between schema versions to detect potential breaking changes.
    Uses the existing SchemaValidator to perform validation and detailed error analysis.
    """
    
    def __init__(self):
        """Initialize the schema compatibility validator."""
        self.validator = SchemaValidator()
        
    def is_backwards_compatible(self, old_schema: Dict[str, Any], 
                               new_schema: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Check if the new schema is backwards compatible with the old schema.
        A schema is backwards compatible if all data valid against the old schema
        is also valid against the new schema.
        
        Args:
            old_schema: The original schema
            new_schema: The new schema to check compatibility with
            
        Returns:
            Tuple of (is_compatible, list of detected compatibility issues)
        """
        # If schemas are identical, they are compatible
        if old_schema == new_schema:
            return True, []
        
        # Generate sample data that conforms to the old schema
        sample_data = list(self.generate_samples_from_schema(old_schema, num_samples=10))
        
        # Validate all samples against the new schema
        incompatible_samples = []
        for data in sample_data:
            # Validate with the new schema
            is_valid, errors = self.validator.validate(data, new_schema)
            
            if not is_valid:
                incompatible_samples.append({
                    'data': data,
                    'errors': errors
                })
                
        # Return compatibility result
        is_compatible = len(incompatible_samples) == 0
        return is_compatible, incompatible_samples
    
    def analyze_compatibility(self, old_schema: Dict[str, Any], 
                             new_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a comprehensive compatibility analysis between two schema versions.
        
        Args:
            old_schema: The original schema
            new_schema: The new schema to analyze
            
        Returns:
            Dictionary containing compatibility analysis results
        """
        result = {
            'is_backwards_compatible': False,
            'breaking_changes': [],
            'added_constraints': [],
            'relaxed_constraints': []
        }
        
        # Check backwards compatibility
        is_compatible, issues = self.is_backwards_compatible(old_schema, new_schema)
        result['is_backwards_compatible'] = is_compatible
        
        # If compatible, we can stop here
        if is_compatible:
            return result
            
        # Analyze specific breaking changes
        
        # 1. Check for required field changes
        old_required = set(old_schema.get('required', []))
        new_required = set(new_schema.get('required', []))
        
        newly_required = new_required - old_required
        if newly_required:
            for field in newly_required:
                result['breaking_changes'].append({
                    'type': 'newly_required_field',
                    'field': field,
                    'severity': 'high'
                })
        
        # 2. Check property type changes
        old_props = old_schema.get('properties', {})
        new_props = new_schema.get('properties', {})
        
        for prop, old_def in old_props.items():
            # Skip if property doesn't exist in new schema (handled elsewhere)
            if prop not in new_props:
                continue
                
            new_def = new_props[prop]
            
            # Check for type changes
            old_type = old_def.get('type')
            new_type = new_def.get('type')
            
            if old_type != new_type and old_type and new_type:
                # Some type changes might not be breaking (e.g., integer -> number)
                safe_type_changes = {('integer', 'number')}
                
                if (old_type, new_type) not in safe_type_changes:
                    result['breaking_changes'].append({
                        'type': 'property_type_change',
                        'field': prop,
                        'from_type': old_type,
                        'to_type': new_type,
                        'severity': 'high'
                    })
            
            # Check for constraint changes (min/max, pattern, etc.)
            self._analyze_constraint_changes(old_def, new_def, prop, result)
                
        # 3. Check for removed properties
        for prop in set(old_props.keys()) - set(new_props.keys()):
            result['breaking_changes'].append({
                'type': 'removed_property',
                'field': prop,
                'severity': 'high' if prop in old_required else 'medium'
            })
            
        # 4. Check for enum value changes
        for prop in set(old_props.keys()) & set(new_props.keys()):
            old_enum = set(old_props[prop].get('enum', []))
            new_enum = set(new_props[prop].get('enum', []))
            
            if old_enum and new_enum:
                removed_values = old_enum - new_enum
                if removed_values:
                    result['breaking_changes'].append({
                        'type': 'removed_enum_values',
                        'field': prop,
                        'removed_values': list(removed_values),
                        'severity': 'high'
                    })
        
        # Determine severity of overall compatibility issues
        severities = [change.get('severity', 'medium') for change in result['breaking_changes']]
        has_high = 'high' in severities
        
        result['compatibility_impact'] = 'high' if has_high else 'medium'
        
        return result
        
    def _analyze_constraint_changes(self, old_def: Dict[str, Any], 
                                  new_def: Dict[str, Any], 
                                  prop: str,
                                  result: Dict[str, Any]) -> None:
        """
        Analyze constraint changes between property definitions.
        
        Args:
            old_def: Old property definition
            new_def: New property definition
            prop: Property name
            result: Result dictionary to update
        """
        constraints = {
            # Numeric constraints
            'minimum': self._is_constraint_tightened_numeric,
            'maximum': self._is_constraint_tightened_numeric,
            'exclusiveMinimum': self._is_constraint_tightened_numeric,
            'exclusiveMaximum': self._is_constraint_tightened_numeric,
            # String constraints
            'minLength': self._is_constraint_tightened_numeric,
            'maxLength': self._is_constraint_tightened_numeric,
            # Array constraints
            'minItems': self._is_constraint_tightened_numeric,
            'maxItems': self._is_constraint_tightened_numeric,
            # Object constraints
            'required': self._is_constraint_tightened_array_length
        }
        
        for constraint, check_func in constraints.items():
            old_value = old_def.get(constraint)
            new_value = new_def.get(constraint)
            
            if old_value is None or new_value is None:
                continue
                
            is_tighter, details = check_func(constraint, old_value, new_value)
            
            if is_tighter:
                result['breaking_changes'].append({
                    'type': 'tightened_constraint',
                    'field': prop,
                    'constraint': constraint,
                    'from': old_value,
                    'to': new_value,
                    'severity': 'medium',
                    'details': details
                })
            elif details:  # Constraint was relaxed
                result['relaxed_constraints'].append({
                    'field': prop,
                    'constraint': constraint,
                    'from': old_value,
                    'to': new_value,
                    'details': details
                })
    
    def _is_constraint_tightened_numeric(self, 
                                       constraint: str, 
                                       old_value: Any, 
                                       new_value: Any) -> Tuple[bool, Dict[str, Any]]:
        """Check if a numeric constraint has been tightened."""
        if constraint in ('minimum', 'exclusiveMinimum', 'minLength', 'minItems'):
            is_tighter = new_value > old_value
            is_relaxed = new_value < old_value
        else:  # maximum, exclusiveMaximum, maxLength, maxItems
            is_tighter = new_value < old_value
            is_relaxed = new_value > old_value
        
        details = None
        if is_tighter:
            details = {'change': 'increased' if constraint.startswith('min') else 'decreased'}
        elif is_relaxed:
            details = {'change': 'decreased' if constraint.startswith('min') else 'increased'}
            
        return is_tighter, details
    
    def _is_constraint_tightened_array_length(self, 
                                           constraint: str, 
                                           old_value: List[Any], 
                                           new_value: List[Any]) -> Tuple[bool, Dict[str, Any]]:
        """Check if an array-length based constraint has been tightened."""
        if constraint == 'required':
            old_set = set(old_value)
            new_set = set(new_value)
            newly_required = new_set - old_set
            no_longer_required = old_set - new_set
            
            is_tighter = len(newly_required) > 0
            is_relaxed = len(no_longer_required) > 0
            
            details = None
            if is_tighter:
                details = {'newly_required': list(newly_required)}
            elif is_relaxed:
                details = {'no_longer_required': list(no_longer_required)}
                
            return is_tighter, details
        
        return False, None
    
    def generate_samples_from_schema(self, schema: Dict[str, Any], 
                                   max_depth: int = 3, 
                                   num_samples: int = 5) -> Generator[Dict[str, Any], None, None]:
        """
        Generate sample data that conforms to the given schema.
        
        Args:
            schema: The JSON schema to generate samples from
            max_depth: Maximum nesting depth for objects
            num_samples: Number of samples to generate
            
        Yields:
            Dict containing sample data that validates against the schema
        """
        if not schema:
            yield {}
            return
            
        # Generate multiple samples
        for _ in range(num_samples):
            yield self._generate_sample(schema, [], max_depth)
    
    def _generate_sample(self, schema: Dict[str, Any], 
                       path: List[str], 
                       max_depth: int) -> Any:
        """Recursive helper to generate a single sample."""
        # Handle different schema types
        schema_type = schema.get('type')
        
        # Handle enums first (regardless of type)
        if 'enum' in schema:
            return random.choice(schema['enum'])
        
        # Handle each type
        if schema_type == 'object':
            return self._generate_object_sample(schema, path, max_depth)
        elif schema_type == 'array':
            return self._generate_array_sample(schema, path, max_depth)
        elif schema_type == 'string':
            return self._generate_string_sample(schema)
        elif schema_type == 'number' or schema_type == 'integer':
            return self._generate_number_sample(schema, schema_type)
        elif schema_type == 'boolean':
            return random.choice([True, False])
        elif schema_type == 'null':
            return None
        
        # Default for unknown types or no type specified
        return "SAMPLE_DATA"
    
    def _generate_object_sample(self, schema: Dict[str, Any], 
                              path: List[str], 
                              max_depth: int) -> Dict[str, Any]:
        """Generate a sample for an object schema."""
        if max_depth <= 0:
            return {}
            
        result = {}
        properties = schema.get('properties', {})
        required = set(schema.get('required', []))
        
        for prop, prop_schema in properties.items():
            # Always include required properties, for non-required use 70% chance
            if prop in required or random.random() < 0.7:
                new_path = path + [prop]
                result[prop] = self._generate_sample(prop_schema, new_path, max_depth - 1)
                
        return result
    
    def _generate_array_sample(self, schema: Dict[str, Any], 
                             path: List[str], 
                             max_depth: int) -> List[Any]:
        """Generate a sample for an array schema."""
        if max_depth <= 0:
            return []
            
        result = []
        items_schema = schema.get('items', {})
        min_items = schema.get('minItems', 1)
        max_items = min(schema.get('maxItems', 3), 5)  # Cap at 5 for practicality
        
        # Generate a random number of items
        num_items = random.randint(min_items, max_items)
        
        for i in range(num_items):
            new_path = path + [str(i)]
            result.append(self._generate_sample(items_schema, new_path, max_depth - 1))
            
        return result
    
    def _generate_string_sample(self, schema: Dict[str, Any]) -> str:
        """Generate a sample for a string schema."""
        # Special formats
        if 'format' in schema:
            fmt = schema['format']
            if fmt == 'date':
                return f"2022-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
            elif fmt == 'date-time':
                return f"2022-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}T{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}Z"
            elif fmt == 'email':
                return f"user{random.randint(1, 999)}@example.com"
            elif fmt == 'uuid':
                return f"{random.randint(0, 0xffffffff):08x}-{random.randint(0, 0xffff):04x}-{random.randint(0, 0xffff):04x}-{random.randint(0, 0xffff):04x}-{random.randint(0, 0xffffffffffff):012x}"
        
        # Handle pattern if specified
        if 'pattern' in schema:
            # Simple pattern handling for common cases
            pattern = schema['pattern']
            if pattern == '^[0-9]{5}$':
                return f"{random.randint(0, 99999):05d}"
            elif pattern == '^[A-Z]{2}$':
                return random.choice(['US', 'UK', 'CA', 'AU', 'JP'])
            
            # For other patterns, fall back to a simple string
        
        # Length constraints
        min_length = schema.get('minLength', 1)
        max_length = min(schema.get('maxLength', 10), 20)  # Cap at 20 for practicality
        
        length = random.randint(min_length, max_length)
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        return ''.join(random.choice(chars) for _ in range(length))
    
    def _generate_number_sample(self, schema: Dict[str, Any], schema_type: str) -> Union[int, float]:
        """Generate a sample for a number or integer schema."""
        min_val = schema.get('minimum', -100)
        max_val = schema.get('maximum', 100)
        
        if schema.get('exclusiveMinimum'):
            min_val += 1
        if schema.get('exclusiveMaximum'):
            max_val -= 1
            
        if schema_type == 'integer':
            return random.randint(min_val, max_val)
        else:  # number
            return round(random.uniform(min_val, max_val), 2)


class EnhancedContractDiffer(ContractDiffer):
    """
    Enhanced version of ContractDiffer that uses SchemaValidator for more
    advanced schema analysis and breaking change detection.
    """
    
    def __init__(self):
        """Initialize the enhanced contract differ."""
        super().__init__()
        self.compat_validator = SchemaCompatibilityValidator()
        
    def diff_request_schema(self, route1: Route, route2: Route) -> SchemaDiff:
        """
        Enhanced version that uses schema validation to detect breaking changes.
        
        Args:
            route1: First route (older version)
            route2: Second route (newer version)
            
        Returns:
            SchemaDiff with additional compatibility information
        """
        # Run the base diff first
        result = super().diff_request_schema(route1, route2)
        
        # Get the schemas
        schema1 = route1.request_schema or {}
        schema2 = route2.request_schema or {}
        
        if not schema1 or not schema2:
            return result  # No additional validation to perform
            
        # Perform compatibility analysis
        compat_analysis = self.compat_validator.analyze_compatibility(schema1, schema2)
        
        # Add compatibility information to the diff result
        result.is_backwards_compatible = compat_analysis.get('is_backwards_compatible', False)
        result.breaking_changes = compat_analysis.get('breaking_changes', [])
        result.compatibility_impact = compat_analysis.get('compatibility_impact', 'unknown')
        
        return result
    
    def diff_response_fields(self, route1: Route, route2: Route) -> ResponseDiff:
        """
        Enhanced version that uses schema validation to detect breaking changes in responses.
        
        Args:
            route1: First route (older version)
            route2: Second route (newer version)
            
        Returns:
            ResponseDiff with additional compatibility information
        """
        # Run the base diff first
        result = super().diff_response_fields(route1, route2)
        
        # Get the responses by status code
        responses1 = {str(r.status_code): r for r in route1.responses}
        responses2 = {str(r.status_code): r for r in route2.responses}
        
        # Only analyze status codes present in both versions
        common_codes = set(responses1.keys()) & set(responses2.keys())
        
        response_analyses = {}
        for code in common_codes:
            resp1 = responses1[code]
            resp2 = responses2[code]
            
            # Skip responses without schemas
            if not resp1.schema or not resp2.schema:
                continue
                
            # Perform compatibility analysis
            compat_analysis = self.compat_validator.analyze_compatibility(resp1.schema, resp2.schema)
            response_analyses[code] = compat_analysis
        
        # Add compatibility information to the diff result
        result.response_compatibility = response_analyses
        
        # Determine if there are any breaking response changes
        has_breaking_changes = any(
            not analysis.get('is_backwards_compatible', True)
            for analysis in response_analyses.values()
        )
        result.has_breaking_response_changes = has_breaking_changes
        
        return result


class EnhancedBreakingChangeClassifier(BreakingChangeClassifier):
    """
    Enhanced breaking change classifier that uses schema compatibility information.
    """
    
    @staticmethod
    def is_breaking_change(change_type: ChangeType, details: Dict[str, Any] = None) -> bool:
        """
        Enhanced classification that also considers schema compatibility information.
        
        Args:
            change_type: The type of change
            details: Additional context about the change
            
        Returns:
            True if this change is breaking for API consumers
        """
        # Use the base classifier first
        is_breaking = BreakingChangeClassifier.is_breaking_change(change_type, details)
        if is_breaking:
            return True
            
        # Additional checks for schema compatibility
        if details:
            # Direct schema compatibility flag
            if details.get('schema_compatibility') is False:
                return True
                
            # Breaking changes detected in schema
            if details.get('breaking_schema_changes'):
                return True
                
            # High severity schema changes
            if details.get('schema_severity') == 'high':
                return True
                
        return is_breaking


class EnhancedDiffFormatter(DiffFormatter):
    """
    Enhanced diff formatter that includes schema compatibility information
    and sample data that demonstrates breaking changes.
    """
    
    @staticmethod
    def generate_change_summaries(diff_result: Dict[str, Any]) -> List[ChangeSummary]:
        """
        Enhanced version that includes schema compatibility information.
        
        Args:
            diff_result: The result from EnhancedContractDiffer.diff_contracts()
            
        Returns:
            List of ChangeSummary objects
        """
        # Generate base summaries
        summaries = DiffFormatter.generate_change_summaries(diff_result)
        classifier = EnhancedBreakingChangeClassifier()
        
        # Add additional schema compatibility summaries
        for path, details in diff_result.get('detailed_diffs', {}).items():
            # Extract method
            method = 'UNKNOWN'
            for route_info in diff_result.get('routes', {}).get('all_routes', []):
                if route_info.get('path') == path:
                    method = route_info.get('method', 'UNKNOWN')
                    break
            
            # Process request schema compatibility
            schema_diff = details.get('request_schema')
            if schema_diff and hasattr(schema_diff, 'breaking_changes'):
                for breaking_change in schema_diff.breaking_changes:
                    change_type = None
                    change_details = {
                        'field': breaking_change.get('field'),
                        'schema_severity': breaking_change.get('severity')
                    }
                    
                    # Map breaking change type to ChangeType
                    if breaking_change.get('type') == 'newly_required_field':
                        change_type = ChangeType.REQUEST_FIELD_NEWLY_REQUIRED
                    elif breaking_change.get('type') == 'property_type_change':
                        change_type = ChangeType.REQUEST_FIELD_MODIFIED
                        change_details['type_changed'] = True
                        change_details['old_type'] = breaking_change.get('from_type')
                        change_details['new_type'] = breaking_change.get('to_type')
                    elif breaking_change.get('type') == 'removed_property':
                        change_type = ChangeType.REQUEST_FIELD_REMOVED
                    elif breaking_change.get('type') == 'tightened_constraint':
                        change_type = ChangeType.REQUEST_FIELD_MODIFIED
                        change_details['constraints_tightened'] = True
                        change_details['constraint'] = breaking_change.get('constraint')
                        change_details['from'] = breaking_change.get('from')
                        change_details['to'] = breaking_change.get('to')
                    
                    if change_type:
                        # Check if this is a breaking change
                        is_breaking = classifier.is_breaking_change(change_type, change_details)
                        
                        summary = ChangeSummary(
                            path=path,
                            method=method,
                            change_type=change_type,
                            is_breaking=is_breaking,
                            details=change_details
                        )
                        summaries.append(summary)
            
            # Process response compatibility
            response_diff = details.get('responses')
            if response_diff and hasattr(response_diff, 'response_compatibility'):
                for status_code, compat_info in response_diff.response_compatibility.items():
                    if not compat_info.get('is_backwards_compatible', True):
                        for breaking_change in compat_info.get('breaking_changes', []):
                            change_type = None
                            change_details = {
                                'field': breaking_change.get('field'),
                                'schema_severity': breaking_change.get('severity'),
                                'status': status_code
                            }
                            
                            # Map breaking change type to ChangeType
                            if breaking_change.get('type') == 'property_type_change':
                                change_type = ChangeType.RESPONSE_FIELD_MODIFIED
                                change_details['type_changed'] = True
                                change_details['old_type'] = breaking_change.get('from_type')
                                change_details['new_type'] = breaking_change.get('to_type')
                            elif breaking_change.get('type') == 'removed_property':
                                change_type = ChangeType.RESPONSE_FIELD_REMOVED
                            
                            if change_type:
                                # Check if this is a breaking change
                                is_breaking = classifier.is_breaking_change(change_type, change_details)
                                
                                summary = ChangeSummary(
                                    path=path,
                                    method=method,
                                    change_type=change_type,
                                    is_breaking=is_breaking,
                                    details=change_details
                                )
                                summaries.append(summary)
        
        return summaries
    
    @staticmethod
    def format_as_markdown(summaries: List[ChangeSummary], 
                          contract_name: str, version1: str, version2: str) -> str:
        """
        Enhanced markdown formatter that includes schema compatibility examples.
        
        Args:
            summaries: List of change summaries
            contract_name: Name of the contract
            version1: First version string
            version2: Second version string
            
        Returns:
            Formatted markdown
        """
        # Get the base markdown
        markdown = DiffFormatter.format_as_markdown(summaries, contract_name, version1, version2)
        
        # Add schema compatibility examples
        schema_examples = [s for s in summaries if s.is_breaking and 
                          s.details.get('schema_example') is not None]
        
        if schema_examples:
            example_section = [
                "\n## Breaking Schema Changes with Examples\n",
                "The following examples demonstrate data that would be valid in the old schema but invalid in the new schema:\n"
            ]
            
            for i, example in enumerate(schema_examples, 1):
                example_section.extend([
                    f"### Example {i}: {example.get_summary_text().replace('[BREAKING] ', '')}",
                    "",
                    "**Valid against old schema but invalid against new schema:**",
                    "```json",
                    json.dumps(example.details.get('schema_example', {}), indent=2),
                    "```",
                    "",
                    "**Validation errors with new schema:**",
                    "```",
                    "\n".join(example.details.get('validation_errors', ["No specific errors available"])),
                    "```",
                    ""
                ])
                
            markdown += "\n".join(example_section)
            
        return markdown


# Example function for generating enhanced diff reports
def generate_enhanced_diff_report(manager: ContractVersionManager, 
                                contract_name: str, 
                                version1: str, 
                                version2: str,
                                format: str = 'markdown') -> str:
    """
    Generate an enhanced diff report with schema validation and compatibility checks.
    
    Args:
        manager: The ContractVersionManager instance
        contract_name: Name of the contract
        version1: First version string
        version2: Second version string
        format: Output format ('text', 'markdown', 'html', or 'json')
        
    Returns:
        Formatted diff report with compatibility information
    """
    # Get the contract versions
    v1 = manager.get_version(contract_name, version1)
    v2 = manager.get_version(contract_name, version2)
    
    if not v1 or not v2:
        raise ValueError(f"One or both versions not found: {version1}, {version2}")
    
    # Load the contracts
    contract1 = manager.load_contract(v1)
    contract2 = manager.load_contract(v2)
    
    # Generate the diff using the enhanced differ
    differ = EnhancedContractDiffer()
    diff_result = differ.diff_contracts(contract1, contract2)
    
    # Generate summaries using the enhanced formatter
    formatter = EnhancedDiffFormatter()
    summaries = formatter.generate_change_summaries(diff_result)
    
    # Format the output
    if format == 'text':
        return formatter.format_as_text(summaries)
    elif format == 'markdown':
        return formatter.format_as_markdown(summaries, contract_name, version1, version2)
    elif format == 'html':
        return formatter.format_as_html(summaries, contract_name, version1, version2)
    elif format == 'json':
        return formatter.format_as_json(summaries, contract_name, version1, version2)
    else:
        raise ValueError(f"Unsupported format: {format}")