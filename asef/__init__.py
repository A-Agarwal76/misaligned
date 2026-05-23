"""
AI Safety Evaluation Framework (ASEF)
=====================================

A modular, sandboxed research framework for evaluating AI safety properties
including alignment faking, sleeper agents, reward hacking, and other
deceptive behaviors in frontier AI models.

.. warning::
    This framework is intended **exclusively** for defensive AI alignment
    research. All evaluations are designed to improve safety monitoring,
    detection, and mitigation of misaligned AI behaviors. It must not be
    used for offensive purposes, to create harmful AI systems, or to
    bypass safety measures in production deployments.

License: Apache 2.0
"""

__version__ = "0.1.0"
__author__ = "ASEF Contributors"
__description__ = "AI Safety Evaluation Framework for defensive alignment research"

from asef.config import Settings, get_settings

__all__ = [
    "__version__",
    "__author__",
    "__description__",
    "Settings",
    "get_settings",
]
