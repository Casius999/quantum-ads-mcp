"""Google Tag Manager (Tag Manager API v2) connector: read + guarded write.

Server-side GTM is the tagging control plane for the sovereign agency; Consent Mode v2
signals are configured here (consent logic itself is out of scope for this connector).
"""

from .connector import register_gtm

__all__ = ["register_gtm"]
