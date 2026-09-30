"""Print a readable summary table of the Charades labels.

    ./run.sh                 # first 20 videos
    ./run.sh --limit 50
    ./run.sh --id YSKX3      # full labels for one video
"""

from __future__ import annotations

import argparse
import shutil
import sys
import textwrap
from typing import List, Sequence

from .loader import DEFAULT_DATA_DIR, Dataset, DatasetNotFound, Video, load_dataset


def fmt_len(seconds) -> str:
    return "-" if seconds is None else f"{seconds:.1f}s"


def truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"


def print_header(ds: Dataset) -> None:
    s = ds.stats()
    splits = " / ".join(f"{n:,} {name}" for name, n in s["splits"].items())
    print(f"Charades v1: {s['videos']:,} videos ({splits}), {s['classes']} action classes, "
          f"{s['segments']:,} action segments, {s['scenes']} scenes, "
          f"avg {s['avg_length']}s, {s['total_hours']} h total")


def print_table(videos: Sequence[Video], width: int) -> None:
    # Fixed-width columns; the last two share whatever width is left.
    fixed = [("ID", 5), ("Split", 5), ("Scene", 16), ("Length", 6), ("#Act", 4)]
    rest = max(20, width - sum(w for _, w in fixed) - 2 * (len(fixed) + 1))
    act_w, obj_w = rest * 2 // 3, rest - rest * 2 // 3
    cols = fixed + [("Actions", act_w), ("Objects", obj_w)]

    def line(values: List[str]) -> str:
        return "  ".join(truncate(v, w).ljust(w) for v, (_, w) in zip(values, cols)).rstrip()

    print(line([name for name, _ in cols]))
    print(line(["-" * w for _, w in cols]))
    for v in videos:
        print(line([
            v.id, v.split, v.scene_short, fmt_len(v.length), str(len(v.actions)),
            "; ".join(v.action_names) or "(none)", ", ".join(v.objects) or "-",
        ]))


def print_detail(v: Video, width: int) -> None:
    wrap = lambda text, indent="  ": textwrap.fill(text, width, initial_indent=indent, subsequent_indent=indent)
    print(f"Video {v.id}  ({v.split}, subject {v.subject})")
    print(f"  Scene:     {v.scene}")
    print(f"  Length:    {fmt_len(v.length)}")
    print(f"  Quality:   {v.quality or '-'} / 7    Relevance: {v.relevance or '-'} / 7    "
          f"Verified: {'yes' if v.verified else 'no'}")
    print(f"  Objects:   {', '.join(v.objects) or '-'}")
    print("\nScript:")
    print(wrap(v.script))
    print("\nDescriptions:")
    for d in v.descriptions:
        print(wrap(d, "  - ").replace("\n  - ", "\n    "))
    print(f"\nAction segments ({len(v.actions)}):")
    for a in sorted(v.actions, key=lambda a: (a.start, a.end)):
        print(f"  {a.start:6.1f}s - {a.end:6.1f}s  {a.code}  {a.name}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run.sh", description="Summarise Charades labels in the terminal.")
    p.add_argument("--id", help="show full labels for one video")
    p.add_argument("--limit", type=int, default=20, help="rows to show (default 20, 0 = all)")
    p.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ds = load_dataset(args.data_dir)
    except DatasetNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    width = shutil.get_terminal_size((120, 24)).columns
    if args.id:
        video = ds.by_id.get(args.id.strip().upper())
        if not video:
            print(f"error: no video with id {args.id!r}", file=sys.stderr)
            return 1
        print_detail(video, width)
        return 0

    print_header(ds)
    print()
    rows = ds.videos if args.limit == 0 else ds.videos[: args.limit]
    print_table(rows, width)
    if len(rows) < len(ds.videos):
        print(f"\n... showing {len(rows)} of {len(ds.videos):,} videos (use --limit 0 for all)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
