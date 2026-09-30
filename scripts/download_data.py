#!/usr/bin/env python3
"""Download the Charades v1 annotation files into ./data.

Only the label files are fetched (a ~3 MB zip). The videos themselves
(13 GB+) are not needed for this tool.

Uses only the standard library, so it runs on a clean machine without curl
or unzip. If the download is blocked, fetch the zip by hand and pass it with
--zip.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

URL = "https://ai2-public-datasets.s3-us-west-2.amazonaws.com/charades/Charades.zip"

# Files the tool needs. The loader fails without these.
REQUIRED = [
    "Charades_v1_train.csv",
    "Charades_v1_test.csv",
    "Charades_v1_classes.txt",
]
# Extra files kept for reference if the zip has them.
OPTIONAL = [
    "Charades_v1_objectclasses.txt",
    "Charades_v1_verbclasses.txt",
    "Charades_v1_mapping.txt",
    "README.txt",
    "license.txt",
]
EXPECTED_COLUMNS = [
    "id", "subject", "scene", "quality", "relevance", "verified",
    "script", "objects", "descriptions", "actions", "length",
]

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = ROOT / "data"


def log(msg: str) -> None:
    print(f"[setup] {msg}", flush=True)


def is_complete(data_dir: Path) -> bool:
    return all((data_dir / name).is_file() for name in REQUIRED)


def download(url: str, dest: Path) -> None:
    """Download url to dest, falling back to curl on SSL certificate errors.

    python.org builds on macOS often ship without CA certificates until
    "Install Certificates.command" is run; the system curl doesn't have
    that problem.
    """
    try:
        _download_urllib(url, dest)
        return
    except urllib.error.URLError as exc:
        if not isinstance(exc.reason, ssl.SSLError):
            raise
        reason = exc.reason
    except ssl.SSLError as exc:
        reason = exc

    curl = shutil.which("curl")
    if not curl:
        raise SystemExit(
            f"SSL error while downloading ({reason}).\n"
            "On macOS with a python.org install, run "
            "'/Applications/Python 3.x/Install Certificates.command' and retry, "
            "or download the zip manually and run: ./setup.sh --zip path/to/Charades.zip"
        )
    log(f"SSL error from Python ({reason}); retrying with curl")
    subprocess.run([curl, "-fL", "--retry", "3", "-o", str(dest), url], check=True)


def _download_urllib(url: str, dest: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "charades-explorer/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 // total
                print(f"\r[setup] downloading... {pct:3d}% ({done / 1e6:.1f} MB)", end="", flush=True)
        if total:
            print(flush=True)


def extract(zip_path: Path, data_dir: Path) -> None:
    """Pull the files we care about out of the zip, flattening any folders.

    Matches by file name rather than by full path, so it doesn't matter
    whether the zip nests everything under a top-level folder.
    """
    wanted = set(REQUIRED + OPTIONAL)
    found = set()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            name = Path(member.filename).name
            if member.is_dir() or name not in wanted or name in found:
                continue
            with zf.open(member) as src, open(data_dir / name, "wb") as dst:
                shutil.copyfileobj(src, dst)
            found.add(name)

    missing = [n for n in REQUIRED if n not in found]
    if missing:
        raise SystemExit(f"Zip is missing expected files: {', '.join(missing)}")


def validate(data_dir: Path) -> None:
    """Sanity-check that the CSVs have the columns the loader expects."""
    for name in ("Charades_v1_train.csv", "Charades_v1_test.csv"):
        with open(data_dir / name, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))
        if header != EXPECTED_COLUMNS:
            raise SystemExit(f"{name}: unexpected columns {header}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zip", type=Path, help="use an already-downloaded Charades.zip instead of downloading")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--force", action="store_true", help="re-download even if data is present")
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    if is_complete(data_dir) and not args.force:
        log(f"annotations already present in {data_dir} (use --force to re-download)")
        return 0

    if args.zip:
        if not args.zip.is_file():
            raise SystemExit(f"--zip: file not found: {args.zip}")
        log(f"using local zip {args.zip}")
        extract(args.zip, data_dir)
    else:
        log(f"downloading {URL}")
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "Charades.zip"
            try:
                download(URL, zip_path)
            except (urllib.error.URLError, OSError, subprocess.CalledProcessError) as exc:
                raise SystemExit(
                    f"Download failed: {exc}\n"
                    f"Download {URL} manually, then run: ./setup.sh --zip path/to/Charades.zip"
                )
            extract(zip_path, data_dir)

    validate(data_dir)
    log(f"done: annotations saved to {data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
