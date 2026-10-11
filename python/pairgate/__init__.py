"""Baseline join ranker.

The join path reads a score card and cached features. It does not load a model.
"""

from pairgate.decide import Decision, RankRequest, decide

__all__ = ["Decision", "RankRequest", "decide"]
