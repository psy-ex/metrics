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

from .metrics import CoreVideo, DstVideo, VideoEnc


def main():
    parser = argparse.ArgumentParser(
        description="Generate statistics for a single video encode."
    )
    parser.add_argument(
        "-i", "--input", required=True, type=str, help="Path to source video file"
    )
    parser.add_argument(
        "-q",
        "--quality",
        required=True,
        type=int,
        help="Desired CRF value for the encoder",
    )
    parser.add_argument(
        "encoder",
        choices=["x264", "x265", "svtav1", "aomenc", "vpxenc"],
        type=str,
        help="Which video encoder to use",
    )
    parser.add_argument("-b", "--keep", type=str, help="Output video file name")
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
    parser.add_argument(
        "-n", "--no-metrics", action="store_true", help="Skip metrics calculations"
    )

    args: Namespace = parser.parse_args()
    src_pth: str = args.input
    dst_pth: str = args.keep
    q: int = args.quality
    enc: str = args.encoder
    every: int = args.every
    enc_args: list[str] = args.encoder_args
    threads: int = args.threads
    gpu_streams: int = args.gpu_streams
    run_metrics: bool = not args.no_metrics

    s: CoreVideo = CoreVideo(src_pth, every, threads, gpu_streams)

    if dst_pth:
        e: VideoEnc = VideoEnc(s, q, enc, enc_args, dst_pth)
    else:
        e: VideoEnc = VideoEnc(s, q, enc, enc_args)
    v: DstVideo = e.encode(every, threads, gpu_streams)
    print(f"Encoded {s.name} --> {e.dst_pth} (took {e.time:.2f} seconds)")

    if run_metrics:
        v.calculate_ssimulacra2(s)
        v.print_ssimulacra2()
        v.calculate_butteraugli(s)
        if gpu_streams:
            v.print_butteraugli()
        v.calculate_ffmpeg_metrics(s)
        v.print_ffmpeg_metrics()

    if not dst_pth:
        e.remove_output()
        print(f"Discarded encode {e.dst_pth}")


if __name__ == "__main__":
    main()
