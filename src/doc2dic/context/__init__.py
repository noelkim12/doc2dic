"""Agent-ready terminology context builders."""

from doc2dic.context.builder import build_explore_context
from doc2dic.context.cards import DEFAULT_EXPLORE_CONTEXT_LIMITS, ExploreContextLimits

__all__ = [
    "DEFAULT_EXPLORE_CONTEXT_LIMITS",
    "ExploreContextLimits",
    "build_explore_context",
]
