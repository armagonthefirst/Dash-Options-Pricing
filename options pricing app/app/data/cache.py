"""Lightweight TTL cache decorator.

Drop-in replacement for ``functools.lru_cache`` that expires entries after
*ttl* seconds.  Keeps the most recent *maxsize* entries.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from functools import wraps
from threading import Lock


def ttl_cache(maxsize: int = 128, ttl: int = 3600):
    """Decorator: cache return values with a per-entry time-to-live.

    Parameters
    ----------
    maxsize : int
        Maximum number of cached entries.  ``None`` means unbounded.
    ttl : int
        Seconds until an entry expires.  Default 3600 (1 hour).
    """

    def decorator(fn):
        cache: OrderedDict[tuple, tuple[float, object]] = OrderedDict()
        lock = Lock()

        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = args + tuple(sorted(kwargs.items()))
            now = time.monotonic()

            with lock:
                if key in cache:
                    ts, value = cache[key]
                    if now - ts < ttl:
                        cache.move_to_end(key)
                        return value
                    else:
                        del cache[key]

            result = fn(*args, **kwargs)

            with lock:
                cache[key] = (time.monotonic(), result)
                if maxsize is not None and len(cache) > maxsize:
                    cache.popitem(last=False)

            return result

        def cache_clear():
            with lock:
                cache.clear()

        wrapper.cache_clear = cache_clear
        return wrapper

    return decorator
