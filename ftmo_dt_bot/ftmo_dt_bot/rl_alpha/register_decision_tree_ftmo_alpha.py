"""register_decision_tree_ftmo_alpha.py - tiny register helper (slot 16)."""
from .decision_tree_ftmo_alpha import DecisionTreeFtmoAlpha


def register(registry):
    return registry.register(DecisionTreeFtmoAlpha())
