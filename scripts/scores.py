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
    parser.add_argument(
        "-c",
        "--csv",
        action="store_true",
        help="Output scores to a CSV file",
    )
    parser.add_argument(
        "-b",
        "--vbutter",
        action="store_true",
        help="Output experimental vButter scores",
    )

    args: Namespace = parser.parse_args()
    every: int = args.every
    csv: bool = args.csv
    vbutter: bool = args.vbutter

    src: CoreVideo = CoreVideo(args.source, every)
    dst: DstVideo = DstVideo(args.distorted, every)

    print(f"Source video:    \033[4m{src.name}\033[0m")
    print(f"Distorted video: \033[4m{dst.name}\033[0m")

    # Calculate SSIMULACRA2 scores
    print("Running \033[94mSSIMULACRA2\033[0m ...")
    dst.calculate_ssimulacra2(src)
    print(f"\033[94mSSIMULACRA2\033[0m scores for every \033[95m{every}\033[0m frame:")
    print(f" Average:       \033[1m{dst.ssimu2_avg:.5f}\033[0m")
    print(f" Harmonic Mean: \033[1m{dst.ssimu2_hmn:.5f}\033[0m")
    print(f" Std Deviation: \033[1m{dst.ssimu2_sdv:.5f}\033[0m")
    print(f" 10th Pctile:   \033[1m{dst.ssimu2_p10:.5f}\033[0m")

    # Calculate Butteraugli scores
    print("Running \033[93mButteraugli\033[0m ...")
    dst.calculate_butteraugli(src)
    print(f"\033[93mButteraugli\033[0m scores for every \033[95m{every}\033[0m frame:")
    print(f" Distance:      \033[1m{dst.butter_dis:.5f}\033[0m")
    print(f" Max Distance:  \033[1m{dst.butter_mds:.5f}\033[0m")
    if vbutter:
        print(f" Average:       \033[1m{dst.butter_avg:.5f}\033[0m")
        print(f" Harmonic Mean: \033[1m{dst.butter_hmn:.5f}\033[0m")
        print(f" Std Deviation: \033[1m{dst.butter_sdv:.5f}\033[0m")
        print(f" 10th Pctile:   \033[1m{dst.butter_p10:.5f}\033[0m")

    # Calculate XPSNR scores
    print("Running \033[91mXPSNR\033[0m ...")
    dst.calculate_xpsnr(src)
    print("\033[91mXPSNR\033[0m scores:")
    print(f" XPSNR Y:       \033[1m{dst.xpsnr_y:.5f}\033[0m")
    print(f" XPSNR U:       \033[1m{dst.xpsnr_u:.5f}\033[0m")
    print(f" XPSNR V:       \033[1m{dst.xpsnr_v:.5f}\033[0m")
    print(f" W-XPSNR:       \033[1m{dst.w_xpsnr:.5f}\033[0m")

    # Write scores to CSV
    if csv:
        dst.write_csvs()


if __name__ == "__main__":
    main()
