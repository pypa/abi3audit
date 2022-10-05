"""
Caching middleware for `abi3audit`.
"""

from requests_cache import CachedSession


def caching_session() -> CachedSession:
    """
    Return a `requests` style session, with suitable caching middleware.
    """

    session = CachedSession("abi3audit", use_cache_dir=True)
    session.max_redirects = 5
    return session
