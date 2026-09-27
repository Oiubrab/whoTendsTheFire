"""The error vocabulary, so failures are typed rather than assorted.

A feature raises one of these; the CLI turns it into a message and a
nonzero exit, the HTTP layer turns it into a status code. Neither layer
needs to know what the feature was doing.
"""


class AppError(Exception):
    """Base class. status is what HTTP should return."""
    status = 500
    label = "error"


class NotFound(AppError):
    status = 404
    label = "not found"


class Invalid(AppError):
    """Bad input from the caller."""
    status = 400
    label = "invalid"


class Conflict(AppError):
    """The request was well-formed but contradicts existing state."""
    status = 409
    label = "conflict"


def as_response(exc):
    """(status, payload) for any exception, typed or not."""
    if isinstance(exc, AppError):
        return exc.status, {"error": exc.label, "detail": str(exc)}
    return 500, {"error": "unexpected", "detail": str(exc)}


def as_exit(exc, stream=None):
    """Print for a human and return the exit code."""
    import sys
    stream = stream or sys.stderr
    if isinstance(exc, AppError):
        print("%s: %s" % (exc.label, exc), file=stream)
        return 1
    print("unexpected error: %s" % exc, file=stream)
    return 2
