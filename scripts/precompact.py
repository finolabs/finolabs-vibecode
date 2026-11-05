#!/usr/bin/env python3
"""Non-blocking PreCompact reminder; no input, files, network or metrics."""

import os


def main():
    try:
        # Unbuffered output avoids a second flush failure at interpreter shutdown.
        os.write(1, b"Before compaction, write back decisions and the next action.\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
