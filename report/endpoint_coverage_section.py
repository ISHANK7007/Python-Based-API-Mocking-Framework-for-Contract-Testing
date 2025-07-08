from report_section import ReportSection
from typing import Dict, List


class EndpointCoverageSection(ReportSection):
    def __init__(self, coverage_data: Dict):
        super().__init__(
            title="API Coverage Analysis",
            description="Analysis of contract-defined endpoints vs. actual usage",
            data=coverage_data
        )
        self.untested_endpoints = [
            path for path, data in coverage_data.items() if not data["is_exercised"]
        ]
        self.partially_tested = [
            path for path, data in coverage_data.items()
            if data["is_exercised"] and data["overall_coverage"] < 100
        ]

    def to_markdown(self) -> str:
        md = f"## {self.title}\n\n{self.description}\n\n"

        total = len(self.data)
        tested = total - len(self.untested_endpoints)
        coverage_pct = (tested / total * 100) if total > 0 else 0

        md += f"**Overall Coverage: {coverage_pct:.1f}%** ({tested}/{total} endpoints exercised)\n\n"

        if self.untested_endpoints:
            md += "### ⚠️ Untested Endpoints\n\n"
            md += "The following endpoints defined in the contract were never called during testing:\n\n"
            for path in sorted(self.untested_endpoints):
                md += f"- `{path}`\n"
            md += "\n"

        md += "### Endpoint Coverage Details\n\n"
        md += "| Endpoint | Status | Methods Tested | Coverage % | Call Count |\n"
        md += "|----------|--------|----------------|------------|------------|\n"

        for path, data in sorted(self.data.items()):
            status = "✅ Tested" if data["is_exercised"] else "⛔ Untested"
            tested_methods = ", ".join(
                [m for m in data["methods"].keys() if data["methods"][m]["is_tested"]]
            ) or ("Partial" if data["is_exercised"] else "None")
            total_calls = sum(m["call_count"] for m in data["methods"].values())
            md += f"| `{path}` | {status} | {tested_methods} | {data['overall_coverage']:.1f}% | {total_calls} |\n"

        return md

    def to_html(self) -> str:
        html = f"<section class='coverage-section'><h2>{self.title}</h2><p>{self.description}</p>"
        total = len(self.data)
        tested = total - len(self.untested_endpoints)
        coverage_pct = (tested / total * 100) if total > 0 else 0
        html += f"<p><strong>Overall Coverage:</strong> {coverage_pct:.1f}% ({tested}/{total} endpoints exercised)</p>"

        if self.untested_endpoints:
            html += "<h3>⚠️ Untested Endpoints</h3><ul>"
            for path in sorted(self.untested_endpoints):
                html += f"<li><code>{path}</code></li>"
            html += "</ul>"

        html += "<h3>Endpoint Coverage Details</h3><table><thead><tr><th>Endpoint</th><th>Status</th><th>Methods Tested</th><th>Coverage %</th><th>Call Count</th></tr></thead><tbody>"
        for path, data in sorted(self.data.items()):
            status = "✅ Tested" if data["is_exercised"] else "⛔ Untested"
            tested_methods = ", ".join(
                [m for m in data["methods"].keys() if data["methods"][m]["is_tested"]]
            ) or ("Partial" if data["is_exercised"] else "None")
            total_calls = sum(m["call_count"] for m in data["methods"].values())
            html += f"<tr><td><code>{path}</code></td><td>{status}</td><td>{tested_methods}</td><td>{data['overall_coverage']:.1f}%</td><td>{total_calls}</td></tr>"
        html += "</tbody></table></section>"
        return html

    def to_json(self) -> Dict:
        return {
            "title": self.title,
            "description": self.description,
            "summary": {
                "total": len(self.data),
                "tested": len(self.data) - len(self.untested_endpoints),
                "untested": self.untested_endpoints,
                "partial": self.partially_tested,
            },
            "details": self.data,
        }

    def to_csv(self) -> str:
        csv = "Endpoint,Status,Methods Tested,Coverage %,Call Count\n"
        for path, data in sorted(self.data.items()):
            status = "Tested" if data["is_exercised"] else "Untested"
            tested_methods = ", ".join(
                [m for m in data["methods"].keys() if data["methods"][m]["is_tested"]]
            ) or ("Partial" if data["is_exercised"] else "None")
            total_calls = sum(m["call_count"] for m in data["methods"].values())
            csv += f"{path},{status},{tested_methods},{data['overall_coverage']:.1f},{total_calls}\n"
        return csv
