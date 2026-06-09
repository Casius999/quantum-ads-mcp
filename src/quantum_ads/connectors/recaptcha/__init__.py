"""reCAPTCHA Enterprise connector: the lead-quality / fraud-signal surface for an ads agency.

Public entry point: :func:`register_recaptcha` mounts both the read and the guarded write tool
planes in one call (site-key listing, assessment creation, and guarded assessment annotation).

The core value is conversion-quality scoring: ``recaptcha.assessment.create`` returns a risk score
in ``[0.0, 1.0]`` (1.0 = very likely legitimate) plus reason codes for a form submission / lead,
so a low-quality or fraudulent lead can be filtered out of conversion uploads before it pollutes
bidding. ``recaptcha.assessment.annotate`` feeds ground-truth LEGITIMATE/FRAUDULENT labels back to
improve the model (guarded write).
"""

from __future__ import annotations

from .connector import register_recaptcha

__all__ = ["register_recaptcha"]
