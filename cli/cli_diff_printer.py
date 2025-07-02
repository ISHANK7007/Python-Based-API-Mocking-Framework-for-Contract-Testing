import click
import os

# Correct imports based on your Output_code structure
from contract.contract_version_manager import ContractVersionManager
from contract.contract_loader import ContractLoader
from contract.contract_entry import ContractEntry
from core.exceptions import ContractNotFoundError

# This function should be defined in a relevant module—import here:
from contract.contract_differ import generate_enhanced_diff_report


@click.command()
@click.argument('contract_name')
@click.option('--from-version', required=True, help="Starting version for comparison")
@click.option('--to-version', help="Target version for comparison (defaults to latest)")
@click.option('--format', default='markdown', type=click.Choice(['text', 'markdown', 'html', 'json']), help="Output format")
@click.option('--output', '-o', help="Output file path (defaults to stdout)")
@click.option('--contracts-dir', default='./contracts', help="Directory containing contract files")
@click.option('--compatibility-only', is_flag=True, help="Only show compatibility-related changes")
@click.option('--show-examples', is_flag=True, help="Include example data that demonstrates breaking changes")
def diff_contracts(contract_name, from_version, to_version, format, output, contracts_dir, compatibility_only, show_examples):
    """Compare two versions of a contract and generate a diff report."""
    try:
        # Initialize the manager
        manager = ContractVersionManager()
        manager.discover_contracts(contracts_dir)

        # If to_version not specified, use the latest
        if not to_version:
            latest = manager.get_latest_version(contract_name)
            if latest:
                to_version = latest.version
            else:
                click.echo(f"Error: No versions found for contract {contract_name}")
                return

        # Generate the enhanced diff report
        report = generate_enhanced_diff_report(
            manager,
            contract_name,
            from_version,
            to_version,
            format=format
        )

        # Output the report
        if output:
            os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
            with open(output, 'w', encoding='utf-8') as f:
                f.write(report)
            click.echo(f"✅ Diff report written to {output}")
        else:
            click.echo(report)

    except Exception as e:
        click.echo(f"❌ Error: {str(e)}")


if __name__ == '__main__':
    diff_contracts()
