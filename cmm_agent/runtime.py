"""Legacy wrapper for the official CMM OS entrypoint."""

from __future__ import annotations

from cmm.__main__ import main as _official_main


def main(argv: list[str] | None = None) -> int:
    return _official_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
