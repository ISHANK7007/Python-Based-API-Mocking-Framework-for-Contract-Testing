from abc import ABC, abstractmethod
from typing import Any, Dict

class ReportSection(ABC):
    """
    Base class for all report sections with format-specific renderers.
    Subclasses must override at least one of the rendering methods.
    """

    def __init__(self, title: str, description: str, data: Any):
        self.title = title
        self.description = description
        self.data = data

    @abstractmethod
    def to_markdown(self) -> str:
        """
        Render this section in Markdown format.
        Subclasses must implement this.
        """
        raise NotImplementedError("Markdown renderer not implemented")

    @abstractmethod
    def to_json(self) -> Dict:
        """
        Render this section in JSON format.
        Subclasses must implement this.
        """
        raise NotImplementedError("JSON renderer not implemented")

    @abstractmethod
    def to_html(self) -> str:
        """
        Render this section in HTML format.
        Subclasses must implement this.
        """
        raise NotImplementedError("HTML renderer not implemented")

    @abstractmethod
    def to_csv(self) -> str:
        """
        Render this section in CSV format.
        Subclasses must implement this.
        """
        raise NotImplementedError("CSV renderer not implemented")
