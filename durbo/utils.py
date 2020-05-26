from typing import Any


def memoize(func: callable) -> callable:
    memoized = {}

    def wrapper(*args) -> Any:
        if args in memoized:
            return memoized[args]
        else:
            rv = func(*args)
            memoized[args] = rv
            return rv

    return wrapper
