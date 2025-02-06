#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13.1"
# dependencies = [
#     "argparse>=1.4.0",
#     "statistics>=1.0.3.5",
#     "tqdm>=4.67.1",
#     "vapoursynth>=70",
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

    args: Namespace = parser.parse_args()
    every: int = args.every

    src: CoreVideo = CoreVideo(args.source, every)
    dst: DstVideo = DstVideo(args.distorted, every)

    print(f"Source video:    \033[4m{src.name}\033[0m")
    print(f"Distorted video: \033[4m{dst.name}\033[0m")

    # Calculate SSIMULACRA2 scores
    print("Running \033[94mSSIMULACRA2\033[0m ...")
    dst.calculate_ssimulacra2(src)
    dst.print_ssimulacra2()

    # Calculate Butteraugli scores
    print("Running \033[93mButteraugli\033[0m ...")
    dst.calculate_butteraugli(src)
    dst.print_butteraugli()

    # Calculate XPSNR scores
    print("Running \033[91mXPSNR\033[0m ...")
    dst.calculate_xpsnr(src)
    dst.print_butteraugli()


if __name__ == "__main__":
    main()
