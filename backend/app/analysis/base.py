from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAnalyzer(ABC):
    """
    Abstract base class for all analyzers.
    Every analyzer must implement the `analyze` method.
    """

    name: str = "base_analyzer"
    description: str = "Base analyzer"

    @abstractmethod
    def analyze(self, target: str, **kwargs) -> Dict[str, Any]:
        """
        Run the analysis on the given target (usually a file path or volume).

        Args:
            target: Path to the evidence file or volume
            **kwargs: Optional extra parameters

        Returns:
            A dictionary containing the analysis results
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"
