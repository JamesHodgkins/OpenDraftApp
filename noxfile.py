import os

import nox


PYTHON = "3.11"


def _qt_headless_env() -> dict[str, str]:
    """
    Mirror the environment flags used in CI for headless Qt stability.

    These are mostly meaningful on Linux CI, but harmless on Windows/macOS.
    """
    return {
        "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "minimal"),
        "QT_OPENGL": os.environ.get("QT_OPENGL", "software"),
        "LIBGL_ALWAYS_SOFTWARE": os.environ.get("LIBGL_ALWAYS_SOFTWARE", "1"),
        "PYTHONFAULTHANDLER": os.environ.get("PYTHONFAULTHANDLER", "1"),
        "PYTHONUNBUFFERED": os.environ.get("PYTHONUNBUFFERED", "1"),
    }


@nox.session(python=PYTHON)
def tests(session: nox.Session) -> None:
    session.install("-r", "requirements.txt")
    session.run(
        "pytest",
        "-ra",
        "-vv",
        "--maxfail=1",
        env={**os.environ, **_qt_headless_env()},
    )


@nox.session(python=PYTHON)
def typecheck(session: nox.Session) -> None:
    session.install("-r", "requirements.txt")
    session.install("pyright")
    # Force import resolution to this session's interpreter (CI parity).
    session.run(
        "pyright",
        "--pythonpath",
        session.python,
    )


@nox.session(python=PYTHON)
def ci(session: nox.Session) -> None:
    """Local equivalent of the GitHub Actions CI job."""
    session.notify("tests")
    session.notify("typecheck")
