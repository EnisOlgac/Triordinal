"""DTree: incremental encoding of directed trees (part of Triordinal).

Since 3.0.0 a DTree keeps one projection, Q1, and its structure in the vertices; DTree 2.x on two
projections remains available as ``triordinal.dtree.two_lists.DTree`` for comparison.
"""

from triordinal.dlist import SINK, SOURCE, DList
from triordinal.dtree.core import DNode, DTree, UMax, UMin, VMax, VMin

__all__ = ["DTree", "DNode", "DList", "VMin", "VMax", "UMin", "UMax", "SOURCE", "SINK"]
__version__ = "3.0.0"
