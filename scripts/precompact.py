#!/usr/bin/env python3
"""Non-blocking PreCompact summary instructions; no network or metrics.

Claude Code uses this output as instructions for the summary, not as a turn for the agent,
so it says what the summary must keep instead of asking for a handover.
"""

import os

INSTRUCTIONS = (b"The summary must keep the goal and acceptance criteria, settled decisions with their dates, "
                b"work in progress, open background runs and pull requests, the next action, and whether a "
                b"handover was saved with handover_state.py.\n")


def main():
    try:
        # Unbuffered output avoids a second flush failure at interpreter shutdown.
        os.write(1, INSTRUCTIONS)
    except Exception:
        pass


if __name__ == "__main__":
    main()
