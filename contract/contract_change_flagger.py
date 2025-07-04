from enum import Enum, auto
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


class ChangeType(Enum):
    ROUTE_ADDED = auto()
    ROUTE_REMOVED = auto()
    ROUTE_MODIFIED = auto()
    REQUEST_FIELD_ADDED = auto()
    REQUEST_FIELD_REMOVED = auto()
    REQUEST_FIELD_MODIFIED = auto()
    REQUEST_FIELD_NEWLY_REQUIRED = auto()
    REQUEST_FIELD_NO_LONGER_REQUIRED = auto()
    RESPONSE_STATUS_ADDED = auto()
    RESPONSE_STATUS_REMOVED = auto()
    RESPONSE_FIELD_ADDED = auto()
    RESPONSE_FIELD_REMOVED = auto()
    RESPONSE_FIELD_MODIFIED = auto()
    RESPONSE_CONTENT_TYPE_CHANGED = auto()


class BreakingChangeClassifier:
    @staticmethod
    def is_breaking_change(change_type: ChangeType, details: Optional[Dict[str, Any]] = None) -> bool:
        always_breaking = {
            ChangeType.ROUTE_REMOVED,
            ChangeType.REQUEST_FIELD_NEWLY_REQUIRED,
            ChangeType.REQUEST_FIELD_REMOVED,
            ChangeType.RESPONSE_STATUS_REMOVED,
            ChangeType.RESPONSE_FIELD_REMOVED
        }

        if change_type in always_breaking:
            return True

        if change_type == ChangeType.ROUTE_MODIFIED:
            return bool(details and details.get('method_changed'))

        if change_type == ChangeType.REQUEST_FIELD_MODIFIED:
            return bool(details and (
                details.get('type_changed') or
                details.get('constraints_tightened')
            ))

        if change_type == ChangeType.RESPONSE_FIELD_MODIFIED:
            return bool(details and details.get('type_changed'))

        if change_type == ChangeType.RESPONSE_CONTENT_TYPE_CHANGED:
            return True

        return False


@dataclass
class ChangeSummary:
    path: str
    method: Optional[str] = None
    change_type: ChangeType = None
    is_breaking: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def get_summary_text(self) -> str:
        prefix = "[BREAKING]" if self.is_breaking else "[NON-BREAKING]"

        ct = self.change_type
        d = self.details
        m = self.method or 'UNKNOWN'
        p = self.path

        if ct == ChangeType.ROUTE_ADDED:
            return f"{prefix} Added route {m} {p}"
        elif ct == ChangeType.ROUTE_REMOVED:
            return f"{prefix} Deleted route {m} {p}"
        elif ct == ChangeType.ROUTE_MODIFIED:
            if d.get("method_changed"):
                return f"{prefix} Changed method from {d.get('old_method')} to {m} for {p}"
            return f"{prefix} Modified route {m} {p}"
        elif ct == ChangeType.REQUEST_FIELD_ADDED:
            field = d.get("field", "unknown")
            optional = " optional" if not d.get("required") else ""
            return f"{prefix} Added{optional} request field '{field}' to {m} {p}"
        elif ct == ChangeType.REQUEST_FIELD_REMOVED:
            return f"{prefix} Removed request field '{d.get('field')}' from {m} {p}"
        elif ct == ChangeType.REQUEST_FIELD_MODIFIED:
            field = d.get("field")
            if d.get("type_changed"):
                return f"{prefix} Changed type of request field '{field}' from {d.get('old_type')} to {d.get('new_type')} in {m} {p}"
            return f"{prefix} Modified request field '{field}' in {m} {p}"
        elif ct == ChangeType.REQUEST_FIELD_NEWLY_REQUIRED:
            return f"{prefix} Field '{d.get('field')}' is now required in {m} {p}"
        elif ct == ChangeType.REQUEST_FIELD_NO_LONGER_REQUIRED:
            return f"{prefix} Field '{d.get('field')}' is no longer required in {m} {p}"
        elif ct == ChangeType.RESPONSE_STATUS_ADDED:
            return f"{prefix} Added response status {d.get('status')} to {m} {p}"
        elif ct == ChangeType.RESPONSE_STATUS_REMOVED:
            return f"{prefix} Removed response status {d.get('status')} from {m} {p}"
        elif ct == ChangeType.RESPONSE_FIELD_ADDED:
            return f"{prefix} Added response field '{d.get('field')}' to status {d.get('status')} in {m} {p}"
        elif ct == ChangeType.RESPONSE_FIELD_REMOVED:
            return f"{prefix} Removed response field '{d.get('field')}' from status {d.get('status')} in {m} {p}"
        elif ct == ChangeType.RESPONSE_FIELD_MODIFIED:
            return f"{prefix} Modified response field '{d.get('field')}' in status {d.get('status')} for {m} {p}"
        elif ct == ChangeType.RESPONSE_CONTENT_TYPE_CHANGED:
            return f"{prefix} Changed response content type from {d.get('old_content_type')} to {d.get('new_content_type')} for status {d.get('status')} in {m} {p}"
        return f"{prefix} Unknown change to {m} {p}"


class DiffFormatter:
    @staticmethod
    def format_as_text(summaries: List[ChangeSummary]) -> str:
        lines = []
        breaking = [s for s in summaries if s.is_breaking]
        non_breaking = [s for s in summaries if not s.is_breaking]

        if breaking:
            lines.append("BREAKING CHANGES:\n" + "=" * 50)
            for s in breaking:
                lines.append(s.get_summary_text())
            lines.append("")

        if non_breaking:
            lines.append("NON-BREAKING CHANGES:\n" + "=" * 50)
            for s in non_breaking:
                lines.append(s.get_summary_text())
        return "\n".join(lines)

    @staticmethod
    def format_as_markdown(summaries: List[ChangeSummary], contract_name: str, version1: str, version2: str) -> str:
        lines = [f"# API Contract Diff: {contract_name}", f"## {version1} → {version2}", ""]
        breaking = [s for s in summaries if s.is_breaking]
        non_breaking = [s for s in summaries if not s.is_breaking]

        lines.append("## Summary\n")
        lines.append(f"- **{len(breaking)}** breaking changes")
        lines.append(f"- **{len(non_breaking)}** non-breaking changes\n")

        if breaking:
            lines.append("## 🚨 Breaking Changes\n")
            for s in breaking:
                lines.append(f"- 🚨 {s.get_summary_text().replace('[BREAKING] ', '')}")
            lines.append("")

        if non_breaking:
            lines.append("## ✅ Non-Breaking Changes\n")
            for s in non_breaking:
                lines.append(f"- ✅ {s.get_summary_text().replace('[NON-BREAKING] ', '')}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_as_html(summaries: List[ChangeSummary], contract_name: str, version1: str, version2: str) -> str:
        html = [f"<h1>API Contract Diff: {contract_name}</h1>",
                f"<h2>{version1} → {version2}</h2>",
                "<hr/>"]

        breaking = [s for s in summaries if s.is_breaking]
        non_breaking = [s for s in summaries if not s.is_breaking]

        html.append(f"<h3>Summary</h3>")
        html.append(f"<ul><li><strong>{len(breaking)}</strong> breaking changes</li>"
                    f"<li><strong>{len(non_breaking)}</strong> non-breaking changes</li></ul>")

        if breaking:
            html.append("<h3 style='color:red;'>🚨 Breaking Changes</h3><ul>")
            for s in breaking:
                html.append(f"<li>{s.get_summary_text().replace('[BREAKING] ', '')}</li>")
            html.append("</ul>")

        if non_breaking:
            html.append("<h3 style='color:green;'>✅ Non-Breaking Changes</h3><ul>")
            for s in non_breaking:
                html.append(f"<li>{s.get_summary_text().replace('[NON-BREAKING] ', '')}</li>")
            html.append("</ul>")

        return "\n".join(html)
