import click
import sys
import json

from contract.compatibility_checker import compatibility_check


@click.command("check-compatibility")
@click.option('--from', 'from_file', required=True, help="Source contract file")
@click.option('--to', 'to_file', required=True, help="Target contract file to compare against")
@click.option('--include-non-breaking', is_flag=True, help="Include non-breaking changes in compatibility assessment")
@click.option('--severity', default="HIGH",
              type=click.Choice(['HIGH', 'MEDIUM', 'LOW', 'INFO'], case_sensitive=False),
              help="Minimum severity level to consider incompatible")
@click.option('--json-output', is_flag=True, help="Output results as JSON")
@click.option('--quiet', is_flag=True, help="Show only the result, no details")
def check_compatibility(from_file, to_file, include_non_breaking, severity, json_output, quiet):
    """
    Check if two contract versions are compatible.

    Example:
        mockapi check-compatibility --from=mock-v1.yaml --to=mock-v2.yaml
    """
    try:
        is_compatible, reasons, details = compatibility_check(
            old_file=from_file,
            new_file=to_file,
            ignore_non_breaking=not include_non_breaking,
            severity_threshold=severity
        )

        if json_output:
            click.echo(json.dumps({
                "is_compatible": is_compatible,
                "reasons": reasons,
                "details": details
            }, indent=2))
            sys.exit(0 if is_compatible else 1)

        if quiet:
            click.echo("COMPATIBLE" if is_compatible else "INCOMPATIBLE")
            sys.exit(0 if is_compatible else 1)

        if is_compatible:
            click.echo(click.style("COMPATIBLE", fg="green", bold=True))
            click.echo("The contracts are compatible.")
        else:
            click.echo(click.style("INCOMPATIBLE", fg="red", bold=True))
            click.echo("The contracts are incompatible for the following reasons:")
            for idx, reason in enumerate(reasons, 1):
                click.echo(f"{idx}. {reason}")

        sys.exit(0 if is_compatible else 1)

    except Exception as e:
        click.echo(click.style(f"Error: {str(e)}", fg="red"), err=True)
        sys.exit(2)
