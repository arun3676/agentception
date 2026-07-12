from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class ResumeTemplate(ABC):
    """Abstract base for resume templates."""

    @abstractmethod
    def generate_pdf(self, tailored_data: Dict[str, Any]) -> bytes:
        """Generate a PDF from tailored resume data."""
        raise NotImplementedError

    @property
    @abstractmethod
    def template_id(self) -> str:
        """Unique template identifier."""
        raise NotImplementedError

    @property
    @abstractmethod
    def template_name(self) -> str:
        """Human-readable template name."""
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """Short template description."""
        raise NotImplementedError

