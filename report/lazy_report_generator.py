import json
from typing import Callable, Dict, Optional, Any


class LazyReportGenerator:
    """Generates report sections on-demand and caches the output."""

    def __init__(self, data_source: Any):
        """
        :param data_source: Object exposing necessary methods or metrics for section generation.
        """
        self.data_source = data_source
        self.generated_sections: Dict[str, str] = {}

    def get_section(self, section_name: str, options: Optional[Dict] = None) -> str:
        """
        Get a report section by name. Generates and caches it if not already generated.
        :param section_name: Logical name of the section (e.g., 'coverage', 'chaos')
        :param options: Optional dict of parameters to influence rendering
        :return: Rendered section string (HTML, Markdown, etc.)
        """
        cache_key = self._create_cache_key(section_name, options)

        if cache_key in self.generated_sections:
            return self.generated_sections[cache_key]

        section = self._generate_section(section_name, options or {})
        self.generated_sections[cache_key] = section
        return section

    def _generate_section(self, section_name: str, options: Dict) -> str:
        """
        Use the appropriate section generator function to produce the report block.
        :param section_name: e.g., 'coverage', 'chaos', etc.
        :param options: Additional arguments passed to the generator
        :return: Rendered section string
        """
        generator = self._get_section_generator(section_name)
        if not generator:
            raise ValueError(f"No generator found for section: {section_name}")
        return generator(options)

    def _get_section_generator(self, section_name: str) -> Optional[Callable[[Dict], str]]:
        """
        Map section names to generator functions.
        This mapping can be dynamic or fixed as needed.
        """
        generators = {
            "coverage": lambda opts: self.data_source.get_coverage_section(opts),
            "chaos": lambda opts: self.data_source.get_chaos_section(opts),
            "drift": lambda opts: self.data_source.get_drift_section(opts),
            "performance": lambda opts: self.data_source.get_performance_section(opts),
        }
        return generators.get(section_name)

    def _create_cache_key(self, section_name: str, options: Optional[Dict]) -> str:
        """
        Create a unique cache key based on section name and serialized options.
        """
        if not options:
            return section_name
        options_str = json.dumps(options, sort_keys=True)
        return f"{section_name}:{options_str}"
