from __future__ import annotations

from typing import Callable, Dict, Any

try:
    from langgraph.graph import StateGraph
except Exception:
    StateGraph = None


def build_learning_graph(handlers: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]]):
    """
    Build a minimal LangGraph workflow for learning + skill gap flows.
    Falls back to None if LangGraph is not installed.
    """
    if StateGraph is None:
        return None
    graph = StateGraph(dict)
    for name, handler in handlers.items():
        graph.add_node(name, handler)
    graph.set_entry_point("learning_path")
    graph.add_edge("learning_path", "skill_gap")
    graph.add_edge("skill_gap", "end")
    return graph.compile()
