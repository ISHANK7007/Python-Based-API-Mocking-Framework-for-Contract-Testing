import click
import os
import sys
import re
from enum import Enum
from typing import Dict, List
from colorama import init, Fore, Style
from tabulate import tabulate

# ✅ Correct imports based on Output_code structure
from contract.contract_loader import ContractLoader
from contract.contract_diff_formatter import EnhancedDiffFormatter
from contract.contract_differ import EnhancedContractDiffer
from contract.contract_diff_types import ChangeType, ChangeSummary


# Severity enum
class Severity(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    def __str__(self):
        return self.value


def get_severity_color(severity: Severity) -> str:
    """Get the appropriate color for a severity level."""
    if severity == Severity.HIGH:
        return Fore.RED
    elif severity == Severity.MEDIUM:
        return Fore.YELLOW
    elif severity == Severity.LOW:
        return Fore.CYAN
    else:  # INFO
        return Fore.GREEN


class SeverityGroupedFormatter:
    """Formats API diff results grouped by severity."""

    @staticmethod
    def map_change_to_severity(change: ChangeSummary) -> Severity:
        """Map a change to a severity level."""
        if change.is_breaking:
            if change.change_type in [
                ChangeType.ROUTE_REMOVED,
                ChangeType.REQUEST_FIELD_NEWLY_REQUIRED,
                ChangeType.RESPONSE_STATUS_REMOVED,
                ChangeType.RESPONSE_FIELD_REMOVED,
            ]:
                return Severity.HIGH
            if change.change_type in [
                ChangeType.REQUEST_FIELD_MODIFIED,
                ChangeType.RESPONSE_FIELD_MODIFIED,
                ChangeType.RESPONSE_CONTENT_TYPE_CHANGED,
            ]:
                return Severity.MEDIUM
            return Severity.HIGH
        if change.change_type in [
            ChangeType.ROUTE_ADDED,
            ChangeType.RESPONSE_STATUS_ADDED,
            ChangeType.REQUEST_FIELD_NO_LONGER_REQUIRED,
        ]:
            return Severity.INFO
        return Severity.LOW

    @staticmethod
    def format_changes_by_severity(summaries: List[ChangeSummary]) -> Dict[Severity, List[ChangeSummary]]:
        result = {
            Severity.HIGH: [],
            Severity.MEDIUM: [],
            Severity.LOW: [],
            Severity.INFO: [],
        }
        for summary in summaries:
            severity = SeverityGroupedFormatter.map_change_to_severity(summary)
            result[severity].append(summary)
        return result

    @staticmethod
    def format_as_text(summaries: List[ChangeSummary], show_details: bool = False) -> str:
        init()
        changes_by_severity = SeverityGroupedFormatter.format_changes_by_severity(summaries)
        lines = []

        lines.append("API COMPATIBILITY REPORT")
        lines.append("=======================\n")

        summary_table = [
            ["HIGH", f"{len(changes_by_severity[Severity.HIGH])} changes", "Breaking changes with high impact"],
            ["MEDIUM", f"{len(changes_by_severity[Severity.MEDIUM])} changes", "Breaking changes with potential workarounds"],
            ["LOW/INFO", f"{len(changes_by_severity[Severity.LOW]) + len(changes_by_severity[Severity.INFO])} changes", "Non-breaking and informational changes"],
        ]

        lines.append("SUMMARY:")
        lines.append(tabulate(summary_table, headers=["Severity", "Count", "Description"]))
        lines.append("")

        for severity in [Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            changes = changes_by_severity[severity]
            if not changes:
                continue
            color = get_severity_color(severity)
            lines.append(f"{color}{severity} SEVERITY CHANGES{Style.RESET_ALL}")
            lines.append("-" * 50)
            for change in changes:
                summary_text = change.get_summary_text().replace("[BREAKING] ", "").replace("[NON-BREAKING] ", "")
                lines.append(f"{color}• {summary_text}{Style.RESET_ALL}")
                if show_details and change.details:
                    for key, value in change.details.items():
                        if key in ['field', 'from_type', 'to_type', 'old_value', 'new_value', 'constraint']:
                            lines.append(f"  - {key}: {value}")
            lines.append("")
        return "\n".join(lines)


@click.group()
def cli():
    """API Mocking Engine CLI."""


@cli.command()
@click.option('--from', 'from_file', required=True, help="Source contract file")
@click.option('--to', 'to_file', required=True, help="Target contract file")
@click.option('--format', 'output_format', default='text', type=click.Choice(['text', 'markdown', 'html', 'json']), help="Output format")
@click.option('--output', '-o', help="Output file path")
@click.option('--details/--no-details', default=False, help="Show detailed information")
@click.option('--examples/--no-examples', default=False, help="Include examples of breaking changes")
@click.option('--color/--no-color', default=True, help="Enable or disable color output")
def diff(from_file, to_file, output_format, output, details, examples, color):
    """Compare two contract files and display a compatibility report grouped by severity."""
    if not os.path.exists(from_file):
        click.echo(f"❌ Error: Source file '{from_file}' not found", err=True)
        sys.exit(1)
    if not os.path.exists(to_file):
        click.echo(f"❌ Error: Target file '{to_file}' not found", err=True)
        sys.exit(1)

    try:
        loader = ContractLoader()
        contract1 = loader.load(from_file)
        contract2 = loader.load(to_file)

        differ = EnhancedContractDiffer()
        formatter = EnhancedDiffFormatter()

        diff_result = differ.diff_contracts(contract1, contract2)
        summaries = formatter.generate_change_summaries(diff_result)

        if output_format == 'text':
            result = SeverityGroupedFormatter.format_as_text(summaries, show_details=details)
        elif output_format == 'markdown':
            result = formatter.format_as_markdown(summaries, "contract", from_file, to_file)
        elif output_format == 'html':
            result = formatter.format_as_html(summaries, "contract", from_file, to_file)
        elif output_format == 'json':
            result = formatter.format_as_json(summaries, "contract", from_file, to_file)
        else:
            click.echo(f"❌ Unsupported format: {output_format}", err=True)
            sys.exit(1)

        if output:
            os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
            with open(output, 'w', encoding='utf-8') as f:
                f.write(result)
            click.echo(f"✅ Diff report written to {output}")
        else:
            if not color:
                result = re.sub(r'\x1b\[\d+m', '', result)
            click.echo(result)

        high_impact = sum(
            1 for s in summaries if SeverityGroupedFormatter.map_change_to_severity(s) == Severity.HIGH
        )
        sys.exit(2 if high_impact else 0)

    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()
