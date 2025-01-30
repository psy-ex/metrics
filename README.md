# Metrics

Run metrics given a source video &amp; a distorted video. Currently supports XPSNR, SSIMULACRA2, and Butteraugli.

## Features

- SSIMULACRA2 scoring (average, harmonic mean, standard deviation, 10th percentile)
- Butteraugli distance metrics
- XPSNR measurements (Y, U, & V channels + weighted XPSNR)
- Optional CSV output
- Frame sampling support for faster metric computation

## Usage

```bash
usage: metrics.py [-h] [-e EVERY] [-c] [-b] source distorted

Run metrics given a source video & a distorted video.

positional arguments:
  source             Source video path
  distorted          Distorted video path

options:
  -h, --help         show this help message and exit
  -e, --every EVERY  Only score every nth frame. Default 1 (every frame)
  -c, --csv          Output scores to a CSV file
  -b, --vbutter      Output experimental vButter scores
```

## Installation

### Dependencies

- [uv](https://github.com/astral-sh/uv/blob/main/README.md), a Python project manager
- FFmpeg >= 7.1 (for XPSNR calculations)
- VapourSynth, and required plugins:
    - ffms2
    - [vszip](https://github.com/dnjulek/vapoursynth-zip)
    - [julek](https://github.com/dnjulek/vapoursynth-julek-plugin)

### Install Instructions

0. Install required dependencies outlined in the previous section

1. Clone the repository

```bash
git clone https://github.com/psy-ex/metrics.git
```

2. Mark the script as executable

```bash
chmod a+x metrics.py
```

3. Run the script

```bash
./metrics.py source.mkv distorted.mkv
```

## Example Output

### Terminal Output

```bash
% ./metrics.py source.mkv distorted.mkv -e 7
Source video:    source.mkv
Distorted video: distorted.mkv
Running SSIMULACRA2 ...
Calculating SSIMULACRA2 scores: 100%|███████████████| 44/44 [00:02<00:00, 18.71 frame/s, avg=59.03]
SSIMULACRA2 scores for every 7 frame:
 Average:       62.00537
 Harmonic Mean: 61.37818
 Std Deviation: 6.26822
 10th Pctile:   54.61722
Running Butteraugli ...
Calculating Butteraugli scores: 100%|████████████████| 44/44 [00:10<00:00,  4.17 frame/s, dis=5.74]
Butteraugli scores for every 7 frame:
 Distance:      6.54400
 Max Distance:  37.98830
Running XPSNR ...
XPSNR scores:
 XPSNR Y:       36.18640
 XPSNR U:       40.47760
 XPSNR V:       40.85780
 W-XPSNR:       37.23460
```

### CSV Output

When using the `-c` option, the script creates a CSV file in a `log_[filename]` directory containing the following metrics:
- Input filesize
- SSIMULACRA2 harmonic mean
- Butteraugli distance
- Weighted XPSNR

These were chosen for CSV output as we believe they are the most relevant statistics for video fidelity assessment.

## License

This project is under the Apache 2.0 license. See the [LICENSE](LICENSE) file for more details.

## Acknowledgements

Thank you @dnjulek for the VapourSynth plugins and @astral-sh for the uv project manager.
