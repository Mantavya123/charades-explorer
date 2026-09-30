"""In-memory search and filtering over loaded Charades videos.

The whole dataset is ~10k rows, so a linear scan over pre-lowercased text is
fast (a few ms per query) and needs no index or external service.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from .loader import Video

# name -> (sort key, reverse)
SORTS: Dict[str, Tuple[Callable[[Video], object], bool]] = {
    "id": (lambda v: v.id, False),
    "longest": (lambda v: v.length or 0.0, True),
    "shortest": (lambda v: v.length or 0.0, False),
    "most-actions": (lambda v: len(v.actions), True),
    "fewest-actions": (lambda v: len(v.actions), False),
}

_TERM_RE = re.compile(r'"([^"]+)"|(\S+)')


def parse_terms(query: str) -> List[str]:
    """Split a query into lowercase terms; "quoted phrases" stay together."""
    return [(phrase or word).lower() for phrase, word in _TERM_RE.findall(query or "")]


def _float_or_none(params: Mapping[str, str], key: str) -> Optional[float]:
    raw = (params.get(key) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{key} must be a number, got {raw!r}")


@dataclass
class Filters:
    q: str = ""                        # keywords: all terms must match (AND)
    scene: str = ""                    # short scene name, e.g. "Kitchen"
    action: str = ""                   # action class code, e.g. "c092"
    object: str = ""                   # object name, e.g. "cup"
    split: str = ""                    # "train" or "test"
    verified: bool = False             # only videos verified against their script
    min_length: Optional[float] = None
    max_length: Optional[float] = None

    @classmethod
    def from_params(cls, params: Mapping[str, str]) -> "Filters":
        """Build filters from query-string style params. Raises ValueError on bad input."""
        get = lambda k: (params.get(k) or "").strip()
        return cls(
            q=get("q"),
            scene=get("scene"),
            action=get("action").lower(),
            object=get("object"),
            split=get("split").lower(),
            verified=get("verified").lower() in ("1", "true", "yes", "on"),
            min_length=_float_or_none(params, "min_length"),
            max_length=_float_or_none(params, "max_length"),
        )


def matches(v: Video, f: Filters, terms: Sequence[str] = ()) -> bool:
    if f.split and v.split != f.split:
        return False
    if f.scene and v.scene_short.lower() != f.scene.lower():
        return False
    if f.verified and not v.verified:
        return False
    if f.min_length is not None and (v.length is None or v.length < f.min_length):
        return False
    if f.max_length is not None and (v.length is None or v.length > f.max_length):
        return False
    if f.action and not any(a.code == f.action for a in v.actions):
        return False
    if f.object and f.object.lower() not in (o.lower() for o in v.objects):
        return False
    return all(t in v.search_text for t in terms)


def search(videos: Sequence[Video], f: Filters, sort: str = "id",
           limit: int = 50, offset: int = 0) -> Tuple[int, List[Video]]:
    """Return (total matches, one page of results)."""
    if sort not in SORTS:
        raise ValueError(f"sort must be one of {', '.join(SORTS)}")
    terms = parse_terms(f.q)
    hits = [v for v in videos if matches(v, f, terms)]
    key, reverse = SORTS[sort]
    hits.sort(key=key, reverse=reverse)
    return len(hits), hits[offset: offset + limit]


def facets(videos: Sequence[Video], classes: Mapping[str, str]) -> dict:
    """Options (with counts) for the filter dropdowns."""
    scenes = Counter(v.scene_short for v in videos)
    objects = Counter(o for v in videos for o in set(v.objects))
    # Count videos containing each action, not segments.
    actions = Counter(code for v in videos for code in {a.code for a in v.actions})
    return {
        "scenes": [{"name": n, "count": c} for n, c in sorted(scenes.items())],
        "objects": [{"name": n, "count": c} for n, c in sorted(objects.items())],
        "actions": sorted(
            ({"code": code, "name": classes.get(code, code), "count": c} for code, c in actions.items()),
            key=lambda a: a["name"].lower(),
        ),
        "splits": sorted({v.split for v in videos}),
    }
