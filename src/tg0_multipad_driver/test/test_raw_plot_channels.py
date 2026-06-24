#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


def main() -> int:
    script_path = Path(__file__).parents[1] / "examples" / "raw_plot_channels.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--describe-topics",
            "--output-prefix",
            "/tg0/multipad/raw_plot",
            "--tag-count",
            "2",
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    topics = result.stdout.strip().splitlines()
    assert topics == [
        "/tg0/multipad/raw_plot/tag0/data1",
        "/tg0/multipad/raw_plot/tag0/data2",
        "/tg0/multipad/raw_plot/tag0/data3",
        "/tg0/multipad/raw_plot/tag1/data1",
        "/tg0/multipad/raw_plot/tag1/data2",
        "/tg0/multipad/raw_plot/tag1/data3",
    ]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
