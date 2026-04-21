"""resume_matcher client package.

Only import from here — never import client.py directly from outside clients/.
"""

from src.clients.resume_matcher.client import CrewAIResumeMatcherClient

__all__ = ["CrewAIResumeMatcherClient"]
