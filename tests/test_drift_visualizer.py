import os
import json
from typing import Dict, Any, Optional
from tabulate import tabulate
from colorama import Fore, Style, init

from core.usage_data_processor import UsageDataProcessor
from core.test_coverage_analyzer import TestCoverageAnalyzer
from contract.contract_differ import ContractDriftAnalyzer

init(autoreset=True)

class ContractDiffVisualizer:
    def __init__(self, diff: Dict[str, Any], verbosity: int = 1, use_color: bool = True):
        self.diff = diff
        self.verbosity = verbosity
        self.use_color = use_color

    def _colored(self, text, color):
        if self.use_color:
            return f"{color}{text}{Style.RESET_ALL}"
        return text

    def render_summary_table(self) -> str:
        summary = self.diff.get("summary", {})
        lines = [self._colored("## API Contract Drift Summary", Fore.CYAN), ""]

        summary_table = [
            ["Added Routes", self._colored(str(summary.get("added_routes_count", 0)), Fore.GREEN)],
            ["Removed Routes", self._colored(str(summary.get("removed_routes_count", 0)), Fore.RED)],
            ["Modified Routes", self._colored(str(summary.get("modified_routes_count", 0)), Fore.YELLOW)],
            ["Unchanged Routes", str(summary.get("unchanged_routes_count", 0))],
            ["Total Drift Score", self._colored(str(summary.get("total_drift_score", 0)), Fore.CYAN if summary.get("total_drift_score", 0) > 0 else "")]
        ]

        if "breaking_summary" in self.diff:
            break_summary = self.diff["breaking_summary"]
            summary_table.append(["", ""])
            summary_table.append(["Breaking Changes", self._colored(str(break_summary["total"]), Fore.RED)])
            summary_table.append(["Critical", self._colored(str(break_summary["by_severity"]["critical"]), Fore.RED)])
            summary_table.append(["High", self._colored(str(break_summary["by_severity"]["high"]), Fore.RED)])
            summary_table.append(["Medium", self._colored(str(break_summary["by_severity"]["medium"]), Fore.YELLOW)])

        lines.append(tabulate(summary_table, tablefmt="simple"))
        lines.append("")
        return "\n".join(lines)

    def render_breaking_changes(self) -> str:
        lines = []
        if "breaking_changes" in self.diff and self.diff["breaking_changes"]:
            lines.append(self._colored("## Breaking Changes", Fore.RED))
            lines.append("")
            breaking_table = []

            for change in self.diff["breaking_changes"]:
                severity_color = Fore.RED
                if change["severity"] == "medium":
                    severity_color = Fore.YELLOW
                elif change["severity"] == "low":
                    severity_color = Fore.CYAN

                breaking_table.append([
                    self._colored(change["severity"].upper(), severity_color),
                    change["code"],
                    f"{change['method'].upper()} {change['path']}",
                    change["message"]
                ])

            lines.append(tabulate(
                breaking_table,
                headers=["Severity", "Code", "Endpoint", "Description"],
                tablefmt="grid"
            ))
            lines.append("")

        return "\n".join(lines)

    def render(self) -> str:
        return "\n".join([
            self.render_summary_table(),
            self.render_breaking_changes()
        ])