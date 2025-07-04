import argparse

def add_deprecation_args(parser: argparse.ArgumentParser) -> argparse._ArgumentGroup:
    """
    Adds CLI arguments related to deprecation tracking to the given parser.
    
    Args:
        parser: The argparse parser instance.
    
    Returns:
        The argument group added for deprecation tracking.
    """
    deprecation_group = parser.add_argument_group("Deprecation Tracking")

    deprecation_group.add_argument(
        "--check-deprecated",
        action="store_true",
        help="Check for newly deprecated routes"
    )

    deprecation_group.add_argument(
        "--deprecation-report",
        action="store_true",
        help="Generate a detailed deprecation report with usage data"
    )

    deprecation_group.add_argument(
        "--import-usage-data",
        metavar="FILE",
        help="Path to a usage data file for incorporating into the report"
    )

    deprecation_group.add_argument(
        "--deprecation-exit-code",
        action="store_true",
        help="Return non-zero exit code if newly deprecated routes are found"
    )

    return deprecation_group
