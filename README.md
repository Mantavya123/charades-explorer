# Charades Explorer

A small tool for browsing and searching the labels of the
[Charades](https://prior.allenai.org/projects/charades) video dataset.

> Work in progress: this stage only downloads the dataset.

## Dataset

**Charades v1** (Allen Institute for AI, 2016): 9,848 videos of everyday
indoor activities, with 66,500 timestamped action segments across 157
action classes, plus scene, duration, objects, scripts and free-text
descriptions for every video.

The labels come as a 3 MB zip of CSV files, which `setup.sh` downloads.
The videos (13 GB+) aren't needed.

## Setup

```bash
./setup.sh
```

This needs only Python 3 and bash. If the download is blocked on your network,
download [Charades.zip](https://ai2-public-datasets.s3-us-west-2.amazonaws.com/charades/Charades.zip)
yourself and run `./setup.sh --zip path/to/Charades.zip`.
