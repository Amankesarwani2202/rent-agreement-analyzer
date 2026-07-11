"""Rent Agreement Analyzer - core analysis package.

Pure-code (no external API) pipeline for analyzing rent agreements.
UI lives in app.py; everything importable and testable from here.
"""

from rent_analyzer.analyze import analyze_agreement
from rent_analyzer.report import generate_summary

__all__ = ["analyze_agreement", "generate_summary"]
