"""Errors safe to show in the editor."""


class UserError(Exception):
    """Actionable error without exposing internal tracebacks."""


class Cancelled(UserError):
    """A cooperative task cancellation."""
