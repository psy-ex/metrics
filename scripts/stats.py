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
import os
from argparse import Namespace
from metrics import CoreVideo, DstVideo, VideoEnc


def write_stats(name: str, q: int, dst: DstVideo) -> None:
    """
    Write metric stats to a CSV file.
    """

    csv: str = name if name.endswith(".csv") else f"{name}.csv"
    if not os.path.exists(csv):
        with open(csv, "w") as f:
            f.write("q,output_filesize,ssimu2_hmean,butter_distance,wxpsnr\n")
            f.write(f"{q},{dst.size},{dst.ssimu2_hmn},{dst.butter_dis},{dst.w_xpsnr}\n")
    else:
        with open(csv, "a") as f:
            f.write(f"{q},{dst.size},{dst.ssimu2_hmn},{dst.butter_dis},{dst.w_xpsnr}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Process a video file with a given encoder and options."
    )
    parser.add_argument(
        "-i", "--input", required=True, type=str, help="Path to source video file"
    )
    parser.add_argument(
        "-q",
        "--quality",
        required=True,
        type=str,
        help="List of quality values to test (e.g. 20 30 40 50)",
    )
    parser.add_argument(
        "encoder",
        choices=["x264", "x265", "svtav1", "aomenc"],
        type=str,
        help="Which video encoder to use",
    )
    parser.add_argument(
        "-o", "--output", required=True, type=str, help="Path to output CSV file"
    )
    parser.add_argument(
        "-e",
        "--every",
        type=int,
        default=1,
        help="Only score every nth frame. Default 1 (every frame)",
    )
    parser.add_argument(
        "encoder_args",
        nargs=argparse.REMAINDER,
        type=str,
        help="Additional encoder arguments (pass these after a '--' delimiter)",
    )

    args: Namespace = parser.parse_args()
    quality_list: list[int] = [int(q) for q in args.quality.split()]
    src_pth: str = args.input
    enc: str = args.encoder
    enc_args: list[str] = args.encoder_args
    every: int = args.every
    csv_out: str = args.output

    s: CoreVideo = CoreVideo(src_pth, every)
    print(f"Source video: {s.name}")

    print(f"Running encoder at qualities: {quality_list}")
    for q in quality_list:
        print(f"Quality: {q}")

        e: VideoEnc = VideoEnc(src_pth, q, enc, enc_args)
        dst_pth: str = e.encode()
        print(f"Encoded video: {dst_pth}")

        v: DstVideo = DstVideo(dst_pth, every)
        v.calculate_ssimulacra2(s)
        v.calculate_butteraugli(s)
        v.calculate_xpsnr(s)
        write_stats(csv_out, q, v)


if __name__ == "__main__":
    main()
