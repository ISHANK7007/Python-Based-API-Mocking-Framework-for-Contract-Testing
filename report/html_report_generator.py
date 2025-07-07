class HtmlReportGenerator:
    def __init__(self, report_data):
        """
        Initialize the HTML report generator.
        :param report_data: A dict with pre-rendered HTML or raw data for each report section.
        """
        self.report_data = report_data

    def generate(self) -> str:
        html = self._create_html_skeleton()
        html = self._add_header_section(html)
        html = self._add_coverage_section(html)
        html = self._add_chaos_visualizations(html)
        html = self._add_timeline_section(html)
        html = self._add_detail_tables(html)
        html += "</body></html>"
        return html

    def _create_html_skeleton(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Mock API Usage Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f7f7f7; color: #333; }
        h1, h2, h3 { color: #2c3e50; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
        th { background-color: #eee; }
        .section { margin-bottom: 50px; }
        .warning { color: #d35400; font-weight: bold; }
    </style>
</head>
<body>
<h1>Mock API Usage Report</h1>
"""

    def _add_header_section(self, html: str) -> str:
        return html + "<p><strong>Generated Report:</strong> Detailed API usage summary with drift and chaos insights.</p>"

    def _add_coverage_section(self, html: str) -> str:
        coverage_html = self.report_data.get("coverage_section", "")
        return html + f"<div class='section' id='coverage'>{coverage_html}</div>"

    def _add_chaos_visualizations(self, html: str) -> str:
        chaos_html = self.report_data.get("chaos_section", "")
        return html + f"<div class='section' id='chaos'>{chaos_html}</div>"

    def _add_timeline_section(self, html: str) -> str:
        timeline_html = self.report_data.get("timeline_section", "")
        return html + f"<div class='section' id='timeline'>{timeline_html}</div>"

    def _add_detail_tables(self, html: str) -> str:
        details_html = self.report_data.get("details_section", "")
        return html + f"<div class='section' id='details'>{details_html}</div>"
