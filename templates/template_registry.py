import os
import jinja2
from typing import Optional, Dict, Any, List

class TemplateRegistry:
    def __init__(self, user_template_dirs: Optional[List[str]] = None):
        """
        Initialize the Jinja2 environment and register templates.
        :param user_template_dirs: Optional list of user-defined template directories
        """
        self.templates = {}
        self.jinja_env = self._create_jinja_environment(user_template_dirs)
        self._register_built_in_templates()

    def _create_jinja_environment(self, user_template_dirs: Optional[List[str]] = None) -> jinja2.Environment:
        """
        Set up the Jinja2 environment with built-in and user-defined paths.
        """
        base_dir = os.path.join(os.path.dirname(__file__), 'templates')
        search_paths = [base_dir]

        if user_template_dirs:
            search_paths.extend(user_template_dirs)

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(search_paths),
            autoescape=jinja2.select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )

        # Register useful filters
        env.filters['format_datetime'] = lambda dt: dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ''
        env.filters['percentage'] = lambda val: f"{val:.1f}%" if isinstance(val, (int, float)) else val

        return env

    def _register_built_in_templates(self):
        """
        Register all built-in templates for reuse by name.
        """
        self.register_template('summary_dashboard', 'sections/summary.jinja2')
        self.register_template('coverage_report', 'sections/coverage.jinja2')
        self.register_template('chaos_analysis', 'sections/chaos.jinja2')
        self.register_template('contract_drift', 'sections/drift.jinja2')
        self.register_template('html_layout', 'layouts/html.jinja2')
        self.register_template('markdown_layout', 'layouts/markdown.jinja2')

    def register_template(self, name: str, template_path: str):
        """
        Register a template path under a unique name.
        :param name: Unique name to identify this template
        :param template_path: Relative path to the template file
        """
        self.templates[name] = template_path

    def get_template(self, name: str) -> jinja2.Template:
        """
        Retrieve a Jinja2 template by registered name.
        :param name: Name of the registered template
        :raises ValueError: If the template name is not found
        """
        if name not in self.templates:
            raise ValueError(f"Template '{name}' not registered")
        return self.jinja_env.get_template(self.templates[name])

    def render_template(self, name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Render the specified template with the given context.
        :param name: Name of the registered template
        :param context: Dictionary of values to pass to the template
        :return: Rendered template string
        """
        template = self.get_template(name)
        return template.render(**(context or {}))
