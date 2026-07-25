from __future__ import annotations

import sys


def main() -> int:
    step_name = sys.argv[1] if len(sys.argv) > 1 else "validation_step"
    reason = sys.argv[2] if len(sys.argv) > 2 else "not_applicable"

    print(f"{step_name}: not applicable ({reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
