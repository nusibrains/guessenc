"""Guess encoding from response headers and/or page content."""

__all__ = ("infer_encoding",)
__version__ = "0.1"

import codecs
import enum
from typing import Mapping, Optional, Tuple

import chardet
import lxml.html


class Source(enum.Enum):
    """Indicates where our detected encoding came from."""

    CHARSET_HEADER = 0
    META_CHARSET = 1
    META_HTTP_EQUIV = 2
    CHARDET = 3
    COULD_NOT_DETECT = 4


Pair = Tuple[Source, Optional[str]]


def infer_encoding(content: Optional[bytes] = None, headers: Optional[Mapping[str, str]] = None) -> Pair:
    headers = headers or {}
    src, res = infer_from_headers(headers)
    if not res:
        if not content:
            return Source.COULD_NOT_DETECT, None
        src, res = infer_from_content(content)
    return src, codecs.lookup(res).name


def infer_from_content(content: bytes) -> Pair:
    # - <meta charset="UTF-8" />
    # - <meta charset="utf-8" />
    # - <meta charset="utf-8">
    # - <meta charset="gb2312">
    doc = lxml.html.fromstring(content)
    el = doc.find(".//meta[@charset]")
    if el is not None:
        val = el.get("charset")
        if val is not None:
            return Source.META_CHARSET, val

    # - <meta content='text/html; charset=UTF-8' http-equiv='Content-Type'/>
    # - <meta content='text/html; charset=windows-1256' http-equiv='Content-Type' />
    # - <meta http-equiv="Content-Type" content="text/html; charset=cp1256">
    # - <meta http-equiv="Content-Type" content="text/html; charset='LATIN-1'">
    # - <meta http-equiv="Content-Type" content="text/html; charset=gb2312" />
    # N.B.: HTML attribute values *are* case-sensitive.  We also cannot
    # use bool(el)
    for path in (".//meta[@http-equiv='Content-Type']", ".//meta[@http-equiv='content-type']"):
        el = doc.find(path)
        found = el is not None
        if found:
            break
    if found:
        val = el.get("content")
        if val is not None:
            return Source.META_HTTP_EQUIV, parse_mimetype_charset_param(val)

    try:
        return Source.CHARDET, chardet.detect(val)["encoding"]
    except Exception:
        return Source.COULD_NOT_DETECT, None


def infer_from_headers(headers: Mapping[str, str]) -> Pair:
    mtype = headers.get("Content-Type")
    if not mtype:
        return Source.COULD_NOT_DETECT, None
    parsed_mtype = parse_mimetype_charset_param(mtype)
    if parsed_mtype:
        return Source.CHARSET_HEADER, parsed_mtype
    return Source.COULD_NOT_DETECT, None


def parse_mimetype_charset_param(mimetype: str) -> Optional[str]:
    parts = mimetype.split(";")
    for item in parts[1:]:
        if not item:
            continue
        try:
            key, value = item.split("=", 1)
        except ValueError:
            pass
        if key.casefold().strip() == "charset":
            return value.strip(" \"'")
    return None