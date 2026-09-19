"""Wave F — the normalized web capability of CMM OS.

One provider-independent boundary for real web search and source retrieval:
``WebSearchService`` (backend-ordered, normalized results), ``fetch_source``
(safe retrieval with SSRF/size/time guards) and ``WebResearchService`` (a
bounded search → read → answer loop over the canonical model-execution seam
that produces real citations).  Backend identity never escapes this package.
"""

from cmm.web.contracts import (
    Citation,
    FetchedSource,
    FetchRequest,
    WebResultItem,
    WebSearchRequest,
    WebSearchResult,
)
from cmm.web.errors import WEB_ERROR_CODES, WebCapabilityError
from cmm.web.retrieval import fetch_source
from cmm.web.service import WebSearchService

__all__ = [
    "WEB_ERROR_CODES",
    "Citation",
    "FetchedSource",
    "FetchRequest",
    "WebCapabilityError",
    "WebResultItem",
    "WebSearchRequest",
    "WebSearchResult",
    "WebSearchService",
    "fetch_source",
]
