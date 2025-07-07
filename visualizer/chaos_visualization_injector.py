def _add_chaos_visualizations(self, html: str) -> str:
    # Prepare chaos data for visualization
    chaos_data = self._prepare_chaos_visualization_data()

    # Build HTML section with chaos data
    vis_section = """
    <section class="chaos-visualizations">
        <h2>Chaos Injection Visualizations</h2>
        <p>This section summarizes chaos behaviors injected during testing.</p>
        <table>
            <thead>
                <tr>
                    <th>Endpoint</th>
                    <th>Time Window</th>
                    <th>Chaos Type</th>
                    <th>Occurrences</th>
                </tr>
            </thead>
            <tbody>
    """

    for entry in chaos_data:
        vis_section += f"""
            <tr>
                <td><code>{entry['endpoint']}</code></td>
                <td>{entry['time_window']}</td>
                <td>{entry['chaos_type']}</td>
                <td>{entry['count']}</td>
            </tr>
        """

    vis_section += """
            </tbody>
        </table>
    </section>
    """

    return html + vis_section
