"""Parse the Charades v1 label files into plain Python objects.

Charades ships two CSVs (train/test) with one row per video, plus a text file
mapping action class codes to names:

    Charades_v1_classes.txt   "<code> <class name>", one per line
    Charades_v1_train.csv     id,subject,scene,quality,relevance,verified,
    Charades_v1_test.csv      script,objects,descriptions,actions,length

List-valued columns are semicolon-separated. `actions` is a list of
"class start end" triplets in seconds, e.g. "c092 11.90 21.20;c147 0.00 12.60".
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

SPLITS = {"train": "Charades_v1_train.csv", "test": "Charades_v1_test.csv"}
CLASSES_FILE = "Charades_v1_classes.txt"

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class DatasetNotFound(FileNotFoundError):
    pass


@dataclass
class Action:
    code: str        # e.g. "c092"
    name: str        # human-readable class name (falls back to the code if unknown)
    start: float     # seconds
    end: float       # seconds, as annotated (can run slightly past the video length)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict:
        return {"code": self.code, "name": self.name, "start": self.start, "end": self.end}


@dataclass
class Video:
    id: str
    split: str
    subject: str
    scene: str
    quality: Optional[int]      # 1-7, annotator-rated; None if blank
    relevance: Optional[int]    # 1-7, how well the video matches the script
    verified: bool
    script: str
    objects: List[str]
    descriptions: List[str]
    actions: List[Action]
    length: Optional[float]     # seconds
    search_text: str = field(default="", repr=False)

    @property
    def scene_short(self) -> str:
        """Scene without the explanatory text, e.g. "Entryway" rather than
        "Entryway (A hall that is generally located at the entrance of a house)"."""
        return short_scene(self.scene)

    @property
    def action_names(self) -> List[str]:
        """Unique action names in order of first appearance."""
        seen: Dict[str, None] = {}
        for a in self.actions:
            seen.setdefault(a.name, None)
        return list(seen)

    def summary_dict(self) -> dict:
        """Compact form for tables and list views."""
        return {
            "id": self.id,
            "split": self.split,
            "scene": self.scene_short,
            "length": self.length,
            "verified": self.verified,
            "num_actions": len(self.actions),
            "actions": self.action_names,
            "objects": self.objects,
        }

    def detail_dict(self) -> dict:
        return {
            **self.summary_dict(),
            "scene_full": self.scene,
            "subject": self.subject,
            "quality": self.quality,
            "relevance": self.relevance,
            "script": self.script,
            "descriptions": self.descriptions,
            "segments": [a.to_dict() for a in sorted(self.actions, key=lambda a: (a.start, a.end))],
        }


@dataclass
class Dataset:
    videos: List[Video]
    classes: Dict[str, str]
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.by_id = {v.id: v for v in self.videos}

    def stats(self) -> dict:
        splits: Dict[str, int] = {}
        for v in self.videos:
            splits[v.split] = splits.get(v.split, 0) + 1
        lengths = [v.length for v in self.videos if v.length is not None]
        return {
            "videos": len(self.videos),
            "splits": splits,
            "classes": len(self.classes),
            "segments": sum(len(v.actions) for v in self.videos),
            "scenes": len({v.scene for v in self.videos}),
            "avg_length": round(sum(lengths) / len(lengths), 1) if lengths else None,
            "total_hours": round(sum(lengths) / 3600, 1) if lengths else None,
        }


# ---------------------------------------------------------------------------
# Parsing helpers

def short_scene(scene: str) -> str:
    return re.sub(r"\s*\(.*\)\s*$", "", scene).strip() or scene


def split_list(value: str) -> List[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def parse_int(value: str) -> Optional[int]:
    value = value.strip()
    return int(value) if value.isdigit() else None


def parse_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except ValueError:
        return None


def load_classes(path: Path) -> Dict[str, str]:
    classes: Dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                classes[parts[0]] = parts[1]
    return classes


def parse_actions(value: str, classes: Dict[str, str], warnings: List[str], video_id: str) -> List[Action]:
    actions = []
    for triplet in split_list(value):
        parts = triplet.split()
        start = parse_float(parts[1]) if len(parts) == 3 else None
        end = parse_float(parts[2]) if len(parts) == 3 else None
        if start is None or end is None:
            warnings.append(f"{video_id}: skipped malformed action {triplet!r}")
            continue
        code = parts[0]
        actions.append(Action(code=code, name=classes.get(code, code), start=start, end=end))
    return actions


def parse_row(row: Dict[str, str], split: str, classes: Dict[str, str], warnings: List[str]) -> Video:
    video = Video(
        id=row["id"].strip(),
        split=split,
        subject=row["subject"].strip(),
        scene=row["scene"].strip(),
        quality=parse_int(row["quality"]),
        relevance=parse_int(row["relevance"]),
        verified=row["verified"].strip().lower() == "yes",
        script=row["script"].strip(),
        objects=split_list(row["objects"]),
        descriptions=split_list(row["descriptions"]),
        actions=parse_actions(row["actions"], classes, warnings, row["id"]),
        length=parse_float(row["length"]),
    )
    # Pre-computed lowercase text used by keyword search.
    video.search_text = " ".join(
        [video.id, video.scene, video.script, *video.objects, *video.descriptions,
         *video.action_names, *(a.code for a in video.actions)]
    ).lower()
    return video


def load_dataset(data_dir: Path = DEFAULT_DATA_DIR) -> Dataset:
    data_dir = Path(data_dir)
    classes_path = data_dir / CLASSES_FILE
    missing = [p.name for p in [classes_path, *(data_dir / f for f in SPLITS.values())] if not p.is_file()]
    if missing:
        raise DatasetNotFound(
            f"Missing {', '.join(missing)} in {data_dir}. Run ./setup.sh first."
        )

    classes = load_classes(classes_path)
    videos: List[Video] = []
    warnings: List[str] = []
    for split, filename in SPLITS.items():
        with open(data_dir / filename, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                videos.append(parse_row(row, split, classes, warnings))
    return Dataset(videos=videos, classes=classes, warnings=warnings)
