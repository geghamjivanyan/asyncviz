"""Packaging utility helpers.

Reserved for cross-platform path helpers and artifact-name parsers
that aren't critical to the core packaging surface but are useful for
release tooling. Kept as an empty package today so callers can
``from asyncviz.packaging.utils import ...`` without an ImportError
once we land helpers here.
"""
