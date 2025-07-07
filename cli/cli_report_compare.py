import click

@click.command("compare")
@click.argument("base_report", type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True))
@click.argument("current_report", type=click.Path(exists=True, file_okay=True, dir_okay=False, readable=True))
@click.option("--output", "-o", type=click.Path(file_okay=True, dir_okay=False, writable=True), 
              help="Path to write comparison report")
@click.option("--format", "-f", type=click.Choice(["html", "json", "markdown", "terminal"]), default="terminal",
              help="Format of the comparison report")
@click.option("--focus", multiple=True, 
              type=click.Choice(["coverage", "chaos", "contract", "performance"]),
              help="Focus comparison on specific aspects (can specify multiple)")
@click.option("--threshold", "-t", type=float, default=5.0,
              help="Highlight changes above this percentage (default: 5.0)")
@click.option("--include-improved/--only-regressions", default=True,
              help="Include improvements or only show regressions")
@click.option("--summary-only", is_flag=True,
              help="Only show summary statistics, not detailed changes")
def compare_reports(base_report, current_report, output, format, focus, 
                   threshold, include_improved, summary_only):
    """
    Compare two API contract test reports and highlight differences.
    
    BASE_REPORT: Path to the older/baseline report file (JSON format)
    CURRENT_REPORT: Path to the newer/current report file (JSON format)
    """
    # TODO: Load and diff base_report and current_report JSON files
    # Use threshold and focus to filter changes
    # Format and print or write to output
    pass
