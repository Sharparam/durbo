import shutil
from os.path import splitext
from tempfile import mkstemp
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen


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


def download_file(url: str, ext: str = None) -> str:
    suffix = None
    if ext:
        suffix = f".{ext}"

    file, path = mkstemp(suffix, 'durbo_')

    with urlopen(url) as response, open(path, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)

    return path


def extension_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path
    _, ext = splitext(path)

    return ext[1:] or None
