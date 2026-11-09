"""Business logic. Services take a Session, validate input and change records.

Routes stay thin: they read the form, call a service, then commit or show the errors.
"""

MAX_ID_DIGITS = 9  # well inside SQLite's 64-bit integers


def parse_id(raw: str | None) -> int | None:
    """A record id from form text, or None if it isn't a plain whole number (digits only).

    str.isdigit() alone accepts characters like "²" that int() rejects, and a very long
    number would overflow SQLite's integer, so both are checked here.
    """
    raw = (raw or "").strip()
    if raw.isascii() and raw.isdigit() and len(raw) <= MAX_ID_DIGITS:
        return int(raw)
    return None


class InvalidInput(ValueError):
    """Raised when user input fails validation. `errors` maps field name to message."""

    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{field}: {msg}" for field, msg in errors.items()))
        self.errors = errors
