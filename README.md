# Charades Explorer

A small tool for browsing and searching the labels of the
[Charades](https://prior.allenai.org/projects/charades) video dataset: a
terminal summary table, a web UI with keyword search and filters, and a JSON
API. It uses only the Python standard library, so there's nothing to install.

## Summary Card

| #   | Section               | What I did                                                                                                                                                                                       | Confidence | Files                                                                                         | Time |
| --- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :--------: | --------------------------------------------------------------------------------------------- | ---- |
| 1   | Dataset + setup       | Chose **Charades v1** (9,848 videos, ~66.5k timestamped action labels). `setup.sh` fetches the 3 MB label zip with plain Python, with no curl, unzip or pip needed.                              |    5/5     | [setup.sh](setup.sh), [download_data.py](scripts/download_data.py)                            |
| 2   | Ingest + summary      | Parser for the Charades CSV label format (action triplets, semicolon lists, blank fields). Terminal summary table and per-video detail view.                                                     |    5/5     | [loader.py](explorer/loader.py), [cli.py](explorer/cli.py), [run.sh](run.sh)                  |
| 3   | Search + filter       | In-memory keyword search (all terms must match, `"quoted phrases"`) plus scene / action / object / split / length / verified filters, in both the web UI and the CLI. Per-video action timeline. |    4/5     | [search.py](explorer/search.py), [server.py](explorer/server.py), [static/](explorer/static/) |
| 4   | README, tests, deploy | This README, 27 unit tests on edge-case fixtures, and `render.yaml` for the optional deploy.                                                                                                     |    4/5     | [README.md](README.md), [tests/](tests/), [render.yaml](render.yaml)                          |

## Quick start

Needs only bash and Python 3.8+ (Mac or Linux).

```bash
./setup.sh      # downloads the Charades labels (~3 MB) into ./data
./run.sh        # web UI at http://localhost:8000
```

Other ways to run it:

```bash
PORT=9000 ./run.sh                                   # different port
./run.sh --cli                                       # summary table in the terminal
./run.sh --cli --q "drinking" --scene Kitchen        # keyword + filters
./run.sh --cli --action c092 --min-length 30 --sort longest
./run.sh --cli --id YSKX3                            # every label for one video
./run.sh --test                                      # unit tests
```

If the download is blocked on your network, download
[Charades.zip](https://ai2-public-datasets.s3-us-west-2.amazonaws.com/charades/Charades.zip)
in a browser and run `./setup.sh --zip path/to/Charades.zip`.

## Dataset: why Charades

**Charades v1** (Allen Institute for AI, ECCV 2016) has 9,848 short videos of
people doing everyday things at home, recorded by 267 crowd workers acting out
scripts. Every video comes with human annotations:

- **Temporal action labels**: 157 action classes, each with a start and end
  time, and several per video (e.g. `c092 11.90 21.20` means action class
  `c092` from 11.9 s to 21.2 s)
- **Metadata**: scene (15 room types), duration, objects present, the
  original script, free-text descriptions from annotators, and quality,
  relevance and verification ratings

Why I picked it:

1. **Video with real, dense labels.** Many overlapping, timestamped actions per
   clip is the kind of annotation a labelling tool deals with, and more
   interesting to summarise and search than one label per clip.
2. **Easy to get.** All labels are in one 3 MB zip on AI2's official mirror,
   with no sign-up and no need to scrape video links.
3. **Rich metadata.** Scene, duration, objects and descriptions give natural
   things to filter on.

Other datasets I considered in the ~30-minute search:

| Dataset          | Why not                                                                                                |
| ---------------- | ------------------------------------------------------------------------------------------------------ |
| Kinetics-700     | One label per clip and little other metadata; the clips are YouTube links, and many have gone offline. |
| ActivityNet v1.3 | Has temporal segments too, but fewer labels per video and again tied to YouTube links.                 |
| AVA              | Bounding boxes plus actions, but tied to feature-film frames and much heavier to work with.            |
| UCF101           | The label is just the folder name; nothing else to summarise.                                          |

## The label format

`Charades_v1_train.csv` and `Charades_v1_test.csv` have one row per video:

| Column                 | Example                                 | Notes                                            |
| ---------------------- | --------------------------------------- | ------------------------------------------------ |
| `id`                   | `YSKX3`                                 | 5-character video ID                             |
| `scene`                | `Bedroom`                               | one of 15 rooms, plus "Other"                    |
| `quality`, `relevance` | `5`, `6`                                | 1–7 annotator ratings (sometimes blank)          |
| `verified`             | `Yes`                                   | annotator confirmed the video matches the script |
| `script`               | `A person fixes the bed…`               | the prompt the actor followed                    |
| `objects`              | `bed;blanket;pillow`                    | semicolon-separated                              |
| `descriptions`         | `A person looks under…;A person is in…` | semicolon-separated, one per annotator           |
| `actions`              | `c077 12.10 18.00;c079 11.80 17.30`     | `class start end` triplets, in seconds           |
| `length`               | `16.62`                                 | seconds                                          |

`Charades_v1_classes.txt` maps each class code to its name, one `<code> <name>` pair per line.

## How it works

```
data/*.csv ──> loader.py ──> search.py ──┬──> cli.py     terminal table
                                          └──> server.py  JSON API + web UI (static/)
```

- **`loader.py`** parses both CSVs into `Video` / `Action` objects and
  pre-computes a lowercase search string per video. Loading all ~10k videos
  takes well under a second.
- **`search.py`** filters with a linear scan. At this size a query takes a few
  milliseconds, so an index or Elasticsearch would add complexity without
  a benefit.
- **`server.py`** is a standard-library `http.server`:
  - `GET /api/meta`: dataset stats and filter options with counts
  - `GET /api/videos?q=&scene=&action=&object=&split=&verified=&min_length=&max_length=&sort=&limit=&offset=`
  - `GET /api/videos/<id>`: all labels for one video
  - `GET /healthz`
- **Web UI**: plain HTML/CSS/JS with no build step and no CDN. Filters are kept
  in the URL, so any view can be shared as a link. Clicking a row opens a panel
  with the script, descriptions, objects and a **timeline of action segments**
  with matching segments emphasised. Supports dark mode and phone widths.
  Press `/` to jump to search and `Esc` to close the panel.

## Assumptions and decisions

- **Labels only, no video files.** The task is about the label format, and
  the videos are 13 GB. The UI therefore has no playback or thumbnails.
- **Train and test are merged** into one list; the `split` column is kept and
  can be filtered.
- **Keyword search** is case-insensitive and matches substrings. Every term
  must match (AND). It searches action names and codes, script,
  descriptions, objects, scene and video ID.
- **Action end times can exceed the video length.** In the test split, about
  30% of segments end up to 1.5 s after the recorded `length`, which looks
  like rounding in the annotation tool. The raw values are kept in the API and
  CLI; the timeline clips them to the video end and shows a note.
- **Bad or unknown values don't crash the loader.** Blank ratings become
  `None`, unknown class codes are shown as the raw code, and malformed action
  triplets are skipped and counted.
- **Long scene names are shortened for display**, e.g. "Entryway (A hall that
  is generally located at the entrance of a house)" becomes "Entryway". The
  full name is in the detail panel.
- **Dataset license.** Charades is licensed for non-commercial research use
  and may not be redistributed, so no data is committed to this repo;
  `setup.sh` downloads it from AI2.

## Tools used

Built with help from an AI assistant (Claude), which the brief allows.

## Deployment (optional bonus)

`render.yaml` deploys the app to Render's free tier: **New → Blueprint →
select this repo**. The build runs `setup.sh` and the start command runs
`run.sh`. The server binds to `0.0.0.0:$PORT` when `PORT` is set.

## Project layout

```
setup.sh, run.sh          entry points
scripts/                  dataset download + Python detection
explorer/loader.py        label parsing
explorer/search.py        filtering, sorting, facets
explorer/cli.py           terminal summary
explorer/server.py        HTTP server + JSON API
explorer/static/          web UI
tests/                    unit tests + small fixture dataset
```

## Reflections

**What would I improve with two more hours?**
Search is plain substring matching. I'd switch to a small inverted index with
relevance ranking, so the best matches come first and typos are tolerated.
The filter counts are currently fixed for the whole dataset; I'd update them
to reflect the current filters. I'd also add a dataset-health view (action
class distribution, videos with low quality ratings or out-of-range segments),
since that's what someone checking label quality would want first. Finally,
I'd put the Charades-specific parsing behind a small adapter interface so the
same UI could load other formats such as Kinetics CSVs or COCO JSON.

**One thing I didn't know how to do, and how I figured it out.**
I usually build servers with Express, so writing one with only Python's
standard library was new to me. I read the `http.server` docs and used
`ThreadingHTTPServer` with a single handler class that routes by path. The
harder part was the "nothing but Python and bash" rule, which ruled out curl,
unzip and pip. I used `urllib` and `zipfile` instead, and added a fallback for
a known macOS problem where python.org builds reject HTTPS certificates until
their certificate installer is run.
