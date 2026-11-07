#!/usr/bin/env python3
"""Non-blocking PreCompact reminder; no network or metrics."""

import os


def main():
    try:
        # Unbuffered output avoids a second flush failure at interpreter shutdown.
        os.write(1, b"Before compaction, write the handover (goal, decisions, work in progress, next action) with handover_state.py write, then write back decisions.\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
