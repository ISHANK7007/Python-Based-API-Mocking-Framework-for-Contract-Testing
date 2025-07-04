def format_changes_as_html(changes):
    """
    Generate HTML output for contract changes grouped by breaking and non-breaking.

    Args:
        changes (List[ChangeSummary]): List of changes to be formatted.

    Returns:
        str: HTML string with formatted changes.
    """
    html = []

    html.append("<html><head><style>")
    html.append("body { font-family: Arial, sans-serif; padding: 20px; }")
    html.append("h2 { color: #333333; }")
    html.append("ul { list-style-type: disc; margin-left: 20px; }")
    html.append("li { margin-bottom: 8px; }")
    html.append(".breaking { color: red; font-weight: bold; }")
    html.append(".non-breaking { color: green; font-weight: bold; }")
    html.append("</style></head><body>")

    html.append("<h2>API Contract Compatibility Report</h2>")

    breaking_route = [s for s in changes if s.is_breaking]
    non_breaking_route = [s for s in changes if not s.is_breaking]

    if breaking_route:
        html.append("<h3 class='breaking'>🚫 Breaking Changes</h3>")
        html.append("<ul>")
        for change in breaking_route:
            summary = change.get_summary_text().replace("[BREAKING] ", "")
            html.append(f"<li><strong>{change.change_type.name}</strong>: {summary}</li>")
        html.append("</ul>")
    else:
        html.append("<p class='breaking'>No breaking changes detected.</p>")

    if non_breaking_route:
        html.append("<h3 class='non-breaking'>✅ Non-Breaking Changes</h3>")
        html.append("<ul>")
        for change in non_breaking_route:
            summary = change.get_summary_text().replace("[NON-BREAKING] ", "")
            html.append(f"<li><strong>{change.change_type.name}</strong>: {summary}</li>")
        html.append("</ul>")
    else:
        html.append("<p class='non-breaking'>No non-breaking changes detected.</p>")

    html.append("</body></html>")

    return "\n".join(html)
