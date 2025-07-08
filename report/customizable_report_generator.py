import yaml
import datetime
from typing import Any, Dict, Optional, List


class CustomizableReportGenerator:
    def __init__(self, data_provider: Any, template_registry: Any, user_template_dirs: Optional[List[str]] = None):
        """
        :param data_provider: Object that exposes get_coverage_data(), get_chaos_data(), etc.
        :param template_registry: An instance of TemplateRegistry
        :param user_template_dirs: Optional list of directories for user-defined templates
        """
        self.data_provider = data_provider
        self.template_registry = template_registry
        self.user_template_dirs = user_template_dirs or []

    def generate_from_layout(self, layout_file: str, output_format: str = 'html') -> str:
        """
        Generate a full report from a YAML layout definition and render using the selected format.
        :param layout_file: Path to the YAML layout config
        :param output_format: 'html', 'markdown', etc.
        :return: Rendered report string
        """
        with open(layout_file, 'r', encoding='utf-8') as f:
            layout = yaml.safe_load(f)

        context = self._prepare_base_context()

        # Render all individual sections
        sections_html = []
        for section_def in layout.get('sections', []):
            section_html = self._render_section(section_def, context)
            sections_html.append(section_html)

        # Render the full layout
        layout_template_name = f"{output_format}_layout"
        full_context = {
            **context,
            "title": layout.get("title", "API Testing Report"),
            "subtitle": layout.get("subtitle", ""),
            "author": layout.get("author", ""),
            "logo": layout.get("logo", None),
            "sections": sections_html,
            "generation_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return self.template_registry.render_template(layout_template_name, full_context)

    def _prepare_base_context(self) -> Dict[str, Any]:
        """
        Load and return all shared metrics and data blocks from the data provider.
        """
        return {
            "coverage_data": self.data_provider.get_coverage_data(),
            "chaos_data": self.data_provider.get_chaos_data(),
            "contract_data": self.data_provider.get_contract_data(),
            "performance_data": self.data_provider.get_performance_data(),
            # Extendable for more data sources
        }

    def _render_section(self, section_def: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Render a section from layout. If it's a 'custom' type, load from path; otherwise, use named template.
        """
        section_type = section_def.get("type", "")
        if section_type == "custom":
            template_path = section_def.get("template")
            if not template_path:
                raise ValueError("Custom section requires a 'template' path.")
            section_context = {**context, **section_def.get("context_variables", {})}
            return self.template_registry.jinja_env.get_template(template_path).render(**section_context)
        else:
            section_context = {
                **context,
                "title": section_def.get("title", ""),
                "config": section_def,
            }
            return self.template_registry.render_template(section_type, section_context)
