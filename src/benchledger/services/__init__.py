"""Business logic. Services take a Session, validate input and change records.

Routes stay thin: they read the form, call a service, then commit or show the errors.
"""


class InvalidInput(ValueError):
    """Raised when user input fails validation. `errors` maps field name to message."""

    def __init__(self, errors: dict[str, str]):
        super().__init__("; ".join(f"{field}: {msg}" for field, msg in errors.items()))
        self.errors = errors
