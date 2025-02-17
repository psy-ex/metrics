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
import os
from argparse import Namespace

from metrics import CoreVideo, DstVideo, VideoEnc


def write_stats(
    name: str,
    q: int,
    size: int,
    ssimu2_hmean: float,
    butter_distance: float,
    w_xpsnr: float,
) -> None:
    """
    Write metric stats to a CSV file.
    """

    csv: str = name if name.endswith(".csv") else f"{name}.csv"
    if not os.path.exists(csv):
        with open(csv, "w") as f:
            f.write("q,output_filesize,ssimu2_hmean,butter_distance,wxpsnr\n")
            f.write(
                f"{q},{size},{ssimu2_hmean:.5f},{butter_distance:.5f},{w_xpsnr:.5f}\n"
            )
    else:
        with open(csv, "a") as f:
            f.write(
                f"{q},{size},{ssimu2_hmean:.5f},{butter_distance:.5f},{w_xpsnr:.5f}\n"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Generate SSIMULACRA2, Butteraugli, and XPSNR statistics for a series of video encodes."
    )
    parser.add_argument(
        "-i",
        "--inputs",
        required=True,
        type=str,
        nargs="+",
        help="Path(s) to source video file(s)",
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
        "-g",
        "--gpu-threads",
        type=int,
        default=0,
        help="Perform SSIMULACRA2 & Butteraugli calculations on the GPU with this many threads",
    )
    parser.add_argument(
        "-k",
        "--keep",
        default=True,
        action="store_false",
        help="Keep output video files",
    )
    parser.add_argument(
        "encoder_args",
        nargs=argparse.REMAINDER,
        type=str,
        help="Additional encoder arguments (pass these after a '--' delimiter)",
    )

    args: Namespace = parser.parse_args()
    src_pth: list[str] = [p for p in args.inputs]
    quality_list: list[int] = [int(q) for q in args.quality.split()]
    enc: str = args.encoder
    csv_out: str = args.output
    every: int = args.every
    gpu_threads: int = args.gpu_threads
    clean: bool = args.keep
    enc_args: list[str] = args.encoder_args

    cumulative_sizes: list[dict[int, int]] = [
        {q: 0 for q in quality_list} for _ in range(len(src_pth))
    ]
    cumulative_ssimu2: list[dict[int, float]] = [
        {q: 0.0 for q in quality_list} for _ in range(len(src_pth))
    ]
    cumulative_butter: list[dict[int, float]] = [
        {q: 0.0 for q in quality_list} for _ in range(len(src_pth))
    ]
    cumulative_wxpsnr: list[dict[int, float]] = [
        {q: 0.0 for q in quality_list} for _ in range(len(src_pth))
    ]
    i: int = 0

    for src in src_pth:
        s: CoreVideo = CoreVideo(src, every, gpu_threads)
        print(f"Source video: {s.name}")

        print(f"Running encoder at qualities: {quality_list}")
        for q in quality_list:
            print(f"Quality: {q}")

            e: VideoEnc = VideoEnc(s, q, enc, enc_args)
            v: DstVideo = e.encode(every, gpu_threads)
            print(f"Encoded video: {e.dst_pth}")

            v.calculate_ssimulacra2(s)
            v.calculate_butteraugli(s)
            v.calculate_xpsnr(s)

            cumulative_sizes[i][q] = v.size
            cumulative_ssimu2[i][q] = v.ssimu2_hmn
            cumulative_butter[i][q] = v.butter_dis
            cumulative_wxpsnr[i][q] = v.w_xpsnr

            if clean:
                e.remove_output()
        i += 1

    avg_size: dict[int, int] = {}
    avg_ssimu2: dict[int, float] = {}
    avg_butter: dict[int, float] = {}
    avg_wxpsnr: dict[int, float] = {}

    for q in quality_list:
        avg_size[q] = int(sum(cumulative_sizes[j][q] for j in range(i)) / i)
        avg_ssimu2[q] = sum(cumulative_ssimu2[j][q] for j in range(i)) / i
        avg_butter[q] = sum(cumulative_butter[j][q] for j in range(i)) / i
        avg_wxpsnr[q] = sum(cumulative_wxpsnr[j][q] for j in range(i)) / i
        write_stats(
            csv_out, q, avg_size[q], avg_ssimu2[q], avg_butter[q], avg_wxpsnr[q]
        )


if __name__ == "__main__":
    main()
