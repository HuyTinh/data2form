"""Generic selector helpers for repeated web-form rows."""


def resolve_row_selector(selector: str, row_index: int, table_mode: bool) -> str:
    """Replace explicit ``{row}`` tokens with a one-based row index."""
    if not table_mode or "{row}" not in selector:
        return selector
    if row_index < 1:
        raise ValueError("row_index must be a positive one-based index")
    return selector.replace("{row}", str(row_index))
