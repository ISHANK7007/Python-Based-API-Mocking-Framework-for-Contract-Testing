from typing import Dict, Any
from tabulate import tabulate
from colorama import Fore, Style

def _generate_table_output(self, diff: Dict[str, Any], verbosity: int, use_color: bool) -> str:
    """Generate tabular output with the specified verbosity level."""
    lines = []

    def colored(text, color):
        return f"{color}{text}{Style.RESET_ALL}" if use_color else text

    # Generate summary
    summary = diff.get("summary", {})
    lines.append(colored("## API Contract Drift Summary", Fore.CYAN))
    lines.append("")

    summary_table = [
        ["Added Routes", colored(str(summary.get("added_routes_count", 0)), Fore.GREEN)],
        ["Removed Routes", colored(str(summary.get("removed_routes_count", 0)), Fore.RED)],
        ["Modified Routes", colored(str(summary.get("modified_routes_count", 0)), Fore.YELLOW)],
        ["Unchanged Routes", str(summary.get("unchanged_routes_count", 0))],
        ["Total Drift Score", colored(str(summary.get("total_drift_score", 0)),
                                     Fore.CYAN if summary.get("total_drift_score", 0) > 0 else Fore.WHITE)]
    ]

    # Add breaking changes summary if available
    break_summary = diff.get("breaking_summary")
    if break_summary:
        lines.append("")
        summary_table.append(["", ""])
        summary_table.append(["Breaking Changes", colored(str(break_summary.get("total", 0)), Fore.RED)])

        by_severity = break_summary.get("by_severity", {})
        summary_table.append(["Critical", colored(str(by_severity.get("critical", 0)), Fore.RED)])
        summary_table.append(["High", colored(str(by_severity.get("high", 0)), Fore.RED)])
        summary_table.append(["Medium", colored(str(by_severity.get("medium", 0)), Fore.YELLOW)])

    lines.append(tabulate(summary_table, tablefmt="simple"))
    lines.append("")

    # Breaking changes section
    breaking_changes = diff.get("breaking_changes", [])
    if breaking_changes:
        lines.append(colored("## Breaking Changes", Fore.RED))
        lines.append("")

        breaking_table = []
        for change in breaking_changes:
            severity = change.get("severity", "unknown").lower()
            severity_color = {
                "critical": Fore.RED,
                "high": Fore.RED,
                "medium": Fore.YELLOW,
                "low": Fore.CYAN
            }.get(severity, Fore.WHITE)

            breaking_table.append([
                colored(severity.upper(), severity_color),
                change.get("code", "N/A"),
                f"{change.get('method', '').upper()} {change.get('path', '')}",
                change.get("message", "")
            ])

        lines.append(tabulate(
            breaking_table,
            headers=["Severity", "Code", "Endpoint", "Description"],
            tablefmt="grid"
        ))
        lines.append("")

    return "\n".join(lines)
