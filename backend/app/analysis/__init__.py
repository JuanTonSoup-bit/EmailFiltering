"""PhishGuard detection engine."""

from .engine import AnalysisResult, analyze
from .message import ParsedMessage

__all__ = ["analyze", "AnalysisResult", "ParsedMessage"]
