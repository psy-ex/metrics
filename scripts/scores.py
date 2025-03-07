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
        "--gpu-threads",
        type=int,
        default=0,
        help="Number of GPU threads for SSIMULACRA2 & Butteraugli",
    )
    parser.add_argument(
        "-c",
        "--cpu-threads",
        type=int,
        default=0,
        help="Number of CPU threads for SSIMULACRA2 (overridden by GPU threads)",
    )

    args: Namespace = parser.parse_args()
    every: int = args.every
    threads: int = args.gpu_threads if args.gpu_threads else args.cpu_threads
    use_gpu: bool = args.gpu_threads > 0

    src: CoreVideo = CoreVideo(args.source, every, threads, use_gpu)
    dst: DstVideo = DstVideo(args.distorted, every, threads, use_gpu)

    print(f"Source video:    \033[4m{src.name}\033[0m")
    print(f"Distorted video: \033[4m{dst.name}\033[0m")

    # Calculate SSIMULACRA2 scores
    print("Running \033[94mSSIMULACRA2\033[0m ...")
    dst.calculate_ssimulacra2(src)
    dst.print_ssimulacra2()

    # Calculate Butteraugli scores
    if use_gpu:
        print("Running \033[93mButteraugli\033[0m ...")
        dst.calculate_butteraugli(src)
        dst.print_butteraugli()
    else:
        dst.calculate_butteraugli(src)

    # Calculate XPSNR scores
    print("Running \033[91mXPSNR\033[0m ...")
    dst.calculate_xpsnr(src)
    dst.print_xpsnr()


if __name__ == "__main__":
    main()
