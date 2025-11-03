"""
Integration hooks para interceptar operações do Verba core
"""

from .import_hook import (
    patch_weaviate_manager,
    patch_verba_manager,
)

__all__ = [
    "patch_weaviate_manager",
    "patch_verba_manager",
]

