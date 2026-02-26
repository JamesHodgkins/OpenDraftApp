"""Module entrypoint for `python -m app`.

This calls the top-level `main.main()` so the project can be run as a package.
"""
import sys

from main import main


if __name__ == "__main__":
    sys.exit(main(sys.argv))
