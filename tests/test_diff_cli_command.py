import os
import shutil
import sys
import click
import unittest

from tests.test_compatibility_checker import TestContractDiffClassification


@click.command("test-diff-scenarios")
@click.option('--create', is_flag=True, help="Create sample contract files for test scenarios")
def test_diff_scenarios(create):
    """
    Run tests against the three key diff scenarios:
    1. Deleted route (breaking)
    2. Added optional field (non-breaking)
    3. Changed type from string to int (breaking)

    Example:
        mockapi test-diff-scenarios
        mockapi test-diff-scenarios --create
    """
    if create:
        # Create a test instance to access its methods
        test_instance = TestContractDiffClassification()
        test_instance.setUp()

        # Create sample files for each scenario
        base_file = test_instance._save_contract_to_temp_file(test_instance.base_contract)
        deleted_route_file = test_instance._save_contract_to_temp_file(
            test_instance._create_contract_with_deleted_route()
        )
        added_field_file = test_instance._save_contract_to_temp_file(
            test_instance._create_contract_with_added_optional_field()
        )
        changed_type_file = test_instance._save_contract_to_temp_file(
            test_instance._create_contract_with_changed_field_type()
        )

        # Create better named copies in the current directory
        shutil.copy(base_file, 'test_base_contract.yaml')
        shutil.copy(deleted_route_file, 'test_deleted_route.yaml')
        shutil.copy(added_field_file, 'test_added_optional_field.yaml')
        shutil.copy(changed_type_file, 'test_changed_type.yaml')

        # Clean up temp files
        os.unlink(base_file)
        os.unlink(deleted_route_file)
        os.unlink(added_field_file)
        os.unlink(changed_type_file)

        click.echo("✅ Created test contract files:")
        click.echo("- test_base_contract.yaml: Base contract")
        click.echo("- test_deleted_route.yaml: Scenario 1 (Deleted route - Breaking)")
        click.echo("- test_added_optional_field.yaml: Scenario 2 (Added optional field - Non-breaking)")
        click.echo("- test_changed_type.yaml: Scenario 3 (Changed type - Breaking)")

        click.echo("\n💡 Example commands to run diffs:")
        click.echo("mockapi diff --from=test_base_contract.yaml --to=test_deleted_route.yaml")
        click.echo("mockapi diff --from=test_base_contract.yaml --to=test_added_optional_field.yaml")
        click.echo("mockapi diff --from=test_base_contract.yaml --to=test_changed_type.yaml")

    else:
        # Run the tests
        suite = unittest.TestSuite()
        suite.addTest(TestContractDiffClassification('test_scenario1_deleted_route_is_breaking'))
        suite.addTest(TestContractDiffClassification('test_scenario2_added_optional_field_is_non_breaking'))
        suite.addTest(TestContractDiffClassification('test_scenario3_changed_type_string_to_int_is_breaking'))
        suite.addTest(TestContractDiffClassification('test_schema_validation_for_incompatible_types'))

        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
