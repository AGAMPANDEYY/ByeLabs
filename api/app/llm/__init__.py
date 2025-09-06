"""
Local LLM Integration Package

This package provides optional local LLM integration for:
- Smarter classification disambiguation
- Better header mapping and column alignment suggestions
- Natural language issue explanations
"""

from .local_llm import LocalLLMClient, get_llm_client

__all__ = ["LocalLLMClient", "get_llm_client"]
