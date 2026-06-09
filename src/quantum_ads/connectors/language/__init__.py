"""Cloud Translation + Natural Language connector: the multi-market localization plane.

Public entry point: :func:`register_language` mounts the language tools onto the FastMCP app.

This is the **localization + content-intelligence** surface, pairing the creative-production
connectors with multi-market reach: Cloud Translation (translate text, detect a language, batch
translate) and Cloud Natural Language (sentiment + entity analysis) so ad content can be localized
and vetted for tone/salient terms before it ships to a market.

All tools are flagged ``read_only=True``: they perform **no account mutation** and are therefore
NOT guarded by the ``WriteExecutor`` (no validate-only preview / two-step confirm). They DO,
however, incur Cloud Translation / Natural Language API cost — the operator controls spend. Every
tool docstring documents this explicitly.

Single backend, keyed ``"language.api"`` (a ``ReadFn``): ``(operation, params) -> result items``
where operation is one of ``"translate"`` / ``"detect"`` / ``"sentiment"`` / ``"entities"`` /
``"batch_translate"``. When it is not wired the tools degrade gracefully, returning a structured
``BACKEND_NOT_CONFIGURED`` error rather than raising.
"""

from .connector import register_language

__all__ = ["register_language"]
