import re
import unicodedata
from datetime import datetime

from autoinput.transforms import transform

_DATE_INPUTS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S")


@transform("strip")
def strip(v: str) -> str:
    return v.strip()


@transform("upper")
def upper(v: str) -> str:
    return v.upper()


@transform("lower")
def lower(v: str) -> str:
    return v.lower()


@transform("title")
def title(v: str) -> str:
    return " ".join(w.capitalize() for w in v.split())


@transform("collapse_spaces")
def collapse_spaces(v: str) -> str:
    return " ".join(v.split())


@transform("digits")
def digits(v: str) -> str:
    return re.sub(r"\D", "", v)


@transform("no_accents")
def no_accents(v: str) -> str:
    text = unicodedata.normalize("NFD", v.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


@transform("replace")
def replace(v: str, old: str, new: str = "") -> str:
    return v.replace(old, new)


@transform("pad_left")
def pad_left(v: str, width: str, char: str = "0") -> str:
    return v.rjust(int(width), char)


@transform("date")
def date(v: str, out_fmt: str = "%d/%m/%Y", in_fmt: str = "") -> str:
    """date:<out>[,<in>] — parse common formats when <in> is omitted."""
    if not v:
        return v
    for fmt in (in_fmt,) if in_fmt else _DATE_INPUTS:
        try:
            return datetime.strptime(v.strip(), fmt).strftime(out_fmt)
        except ValueError:
            continue
    raise ValueError(f"'{v}' is not a recognized date")


@transform("phone_vn")
def phone_vn(v: str) -> str:
    d = digits(v)
    if d.startswith("84"):
        d = "0" + d[2:]
    if not re.fullmatch(r"0\d{9}", d):
        raise ValueError(f"'{v}' is not a valid VN phone number")
    return d


@transform("map")
def map_values(v: str, *pairs: str) -> str:
    """map:Nam=M,Nữ=F — unknown values pass through unchanged."""
    table = dict(p.split("=", 1) for p in pairs if "=" in p)
    return table.get(v, v)
