#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13.1"
# dependencies = [
#     "argparse>=1.4.0",
#     "statistics>=1.0.3.5",
#     "tqdm>=4.67.1",
#     "vapoursynth>=70",
#     "vstools>=3.3.4",
# ]
# ///

import argparse
from argparse import Namespace

from metrics import CoreVideo, DstVideo


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run metrics given a source video & a distorted video."
    )
    parser.add_argument("source", help="Source video path")
    parser.add_argument("distorted", help="Distorted video path")
    parser.add_argument(
        "-e",
        "--every",
        type=int,
        default=1,
        help="Only score every nth frame. Default 1 (every frame)",
    )
    parser.add_argument(
        "-g",
        "--gpu-streams",
        type=int,
        default=0,
        help="Number of GPU streams for SSIMULACRA2/Butteraugli",
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=0,
        help="Number of threads for SSIMULACRA2/Butteraugli",
    )

    args: Namespace = parser.parse_args()
    every: int = args.every
    threads: int = args.threads
    gpu_streams: int = args.gpu_streams

    s: CoreVideo = CoreVideo(args.source, every, threads, gpu_streams)
    v: DstVideo = DstVideo(args.distorted, every, threads, gpu_streams)

    print(f"Source video:    \033[4m{s.name}\033[0m")
    print(f"Distorted video: \033[4m{v.name}\033[0m")

    # Calculate SSIMULACRA2 scores
    v.calculate_ssimulacra2(s)
    v.print_ssimulacra2()

    # Calculate Butteraugli scores
    if gpu_streams:
        v.calculate_butteraugli(s)
        v.print_butteraugli()
    else:
        v.calculate_butteraugli(s)

    # Calculate XPSNR scores
    v.calculate_xpsnr(s)
    v.print_xpsnr()


if __name__ == "__main__":
    main()
