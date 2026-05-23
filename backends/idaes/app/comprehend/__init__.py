"""
Heuristic comprehension layer — infers process role annotations without
an LLM. Fast, deterministic, CI-friendly.

R2 will swap this for Claude when available and keep this module as the
fallback path. Interface is stable: both return ``Annotations`` with the
same shape.
"""
from .annotator import Annotations, BlockAnnotation, annotate, infer_product, infer_feedstock

__all__ = ["Annotations", "BlockAnnotation", "annotate", "infer_product", "infer_feedstock"]
