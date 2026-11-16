def parse_rows(spec: str | None) -> set[int] | None:
    """'1-3,7' -> {1, 2, 3, 7}. Empty -> None (all rows). Raises ValueError on bad input."""
    if not spec or not spec.strip():
        return None
    rows: set[int] = set()
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        start, _, end = part.partition("-")
        lo, hi = int(start), int(end or start)
        if lo < 1 or hi < lo:
            raise ValueError(f"Invalid row range '{part}'")
        rows.update(range(lo, hi + 1))
    return rows
