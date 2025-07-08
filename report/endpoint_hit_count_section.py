from report_section import ReportSection
from typing import List, Dict

class EndpointHitCountSection(ReportSection):
    def __init__(self, endpoint_data: List[Dict]):
        super().__init__(
            title="Endpoint Usage Summary",
            description="Request distribution across API endpoints",
            data=self._process_endpoint_data(endpoint_data)
        )

    def _process_endpoint_data(self, raw_data: List[Dict]) -> List[Dict]:
        # Placeholder logic: sort by hit count descending
        return sorted(raw_data, key=lambda x: x.get("hits", 0), reverse=True)

    def to_markdown(self) -> str:
        md = f"## {self.title}\n\n{self.description}\n\n"
        md += "| Endpoint | Hits | Success % | Avg Time (ms) |\n"
        md += "|----------|------|-----------|----------------|\n"
        for row in self.data:
            md += f"| {row['endpoint']} | {row['hits']} | {row['success_rate']:.1f}% | {row['avg_time_ms']:.2f} |\n"
        return md

    def to_json(self) -> Dict:
        return {"title": self.title, "description": self.description, "data": self.data}

    def to_html(self) -> str:
        html = f"<section><h2>{self.title}</h2><p>{self.description}</p><table><tr><th>Endpoint</th><th>Hits</th><th>Success %</th><th>Avg Time (ms)</th></tr>"
        for row in self.data:
            html += f"<tr><td>{row['endpoint']}</td><td>{row['hits']}</td><td>{row['success_rate']:.1f}%</td><td>{row['avg_time_ms']:.2f}</td></tr>"
        html += "</table></section>"
        return html

    def to_csv(self) -> str:
        csv = "Endpoint,Hits,Success %,Avg Time (ms)\n"
        for row in self.data:
            csv += f"{row['endpoint']},{row['hits']},{row['success_rate']:.1f},{row['avg_time_ms']:.2f}\n"
        return csv
