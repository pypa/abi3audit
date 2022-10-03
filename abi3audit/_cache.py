"""
Caching middleware for `abi3audit`.
"""

from pathlib import Path

import requests
from cachecontrol import CacheControl
from cachecontrol.caches import FileCache

_ABI3AUDIT_INTERNAL_CACHE = Path.home() / ".cache" / "abi3audit"


def caching_session() -> CacheControl:
    """
    Return a `requests` style session, with suitable caching middleware.
    """

    # We limit the number of redirects to 5, since the services we connect to
    # should really never redirect more than once or twice.
    inner_session = requests.Session()
    inner_session.max_redirects = 5

    return CacheControl(
        inner_session,
        cache=FileCache(_ABI3AUDIT_INTERNAL_CACHE),
    )
