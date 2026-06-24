#!/usr/bin/env python3
import subprocess
import os
from pathlib import Path


def main() -> int:
    script_path = Path(__file__).parents[1] / "examples" / "rqt_plot_raw.sh"
    bash = os.environ.get("BASH", "bash")
    if os.name == "nt" and bash == "bash":
        bash = r"C:\Program Files\Git\bin\bash.exe"
    result = subprocess.run(
        [bash, str(script_path), "--dry-run"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    command = result.stdout.strip()

    expected_parts = [
        "ros2",
        "run",
        "rqt_plot",
        "rqt_plot",
        "/tg0/multipad/raw_plot/tag0/data1/data",
        "/tg0/multipad/raw_plot/tag0/data2/data",
        "/tg0/multipad/raw_plot/tag0/data3/data",
    ]
    for part in expected_parts:
        assert part in command, f"missing {part!r} in {command!r}"

    custom = subprocess.run(
        [bash, str(script_path), "--dry-run", "--prefix", "/demo/raw_plot"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()
    assert "/demo/raw_plot/tag0/data1/data" in custom
    assert "/demo/raw_plot/tag0/data0/data" not in custom
    assert "/tg0/multipad/raw_plot/tag0/data1/data" not in custom

    tag_specific = subprocess.run(
        [bash, str(script_path), "--dry-run", "--tag", "3"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()
    assert "/tg0/multipad/raw_plot/tag3/data0/data" not in tag_specific
    assert "/tg0/multipad/raw_plot/tag3/data1/data" in tag_specific
    assert "/tg0/multipad/raw_plot/tag3/data2/data" in tag_specific
    assert "/tg0/multipad/raw_plot/tag3/data3/data" in tag_specific
    assert "/tg0/multipad/raw_plot/tag4/data1/data" not in tag_specific

    multi_tag = subprocess.run(
        [bash, str(script_path), "--dry-run", "--tag", "1", "--tag", "4"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()
    assert "/tg0/multipad/raw_plot/tag1/data0/data" not in multi_tag
    assert "/tg0/multipad/raw_plot/tag1/data1/data" in multi_tag
    assert "/tg0/multipad/raw_plot/tag4/data3/data" in multi_tag
    assert "/tg0/multipad/raw_plot/tag2/data1/data" not in multi_tag

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
