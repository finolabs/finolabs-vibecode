#!/usr/bin/env python3
"""Non-blocking PreCompact reminder; local nonce guard; no network or metrics."""

import os


def main():
    try:
        import sys
        from pathlib import Path
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from quota_probe import worker_guard
        if worker_guard():
            return 0
    except Exception:
        pass
    try:
        # Unbuffered output avoids a second flush failure at interpreter shutdown.
        os.write(1, b"Before compaction, write back decisions and the next action.\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
