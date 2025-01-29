#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13.1"
# dependencies = [
#     "argparse>=1.4.0",
#     "tqdm>=4.67.1",
#     "vapoursynth>=70",
# ]
# ///

import argparse
import math
import os
import re
import subprocess
from argparse import Namespace
from subprocess import Popen
from sys import _xoptions

import vapoursynth as vs
from tqdm import tqdm


class SrcVideo:
    """
    Source video class.
    """

    path: str
    name: str

    def __init__(self, pth: str) -> None:
        self.path = pth
        self.name = os.path.basename(pth)


class DstVideo:
    """
    Distorted video class containing metric scores.
    """

    path: str
    name: str
    # SSIMULACRA2 scores
    ssimu2_avg: float
    ssimu2_hmn: float
    ssimu2_sdv: float
    ssimu2_p10: float
    # Butteraugli scores
    butter_avg: float
    butter_hmn: float
    butter_sdv: float
    butter_p10: float
    # XPSNR scores
    xpsnr_y: float
    xpsnr_u: float
    xpsnr_v: float
    w_xpsnr: float

    def __init__(self, pth: str) -> None:
        self.path = pth
        self.name = os.path.basename(pth)
        self.ssimu2_avg = 0.0
        self.ssimu2_hmn = 0.0
        self.ssimu2_sdv = 0.0
        self.ssimu2_p10 = 0.0
        self.butter_avg = 0.0
        self.butter_hmn = 0.0
        self.butter_sdv = 0.0
        self.butter_p10 = 0.0
        self.xpsnr_y = 0.0
        self.xpsnr_u = 0.0
        self.xpsnr_v = 0.0
        self.w_xpsnr = 0.0

    def calculate_ssimulacra2(self, src: SrcVideo, e: int) -> None:
        """
        Calculate SSIMULACRA2 score between a source video & a distorted video.
        """
        core = vs.core

        src_data = core.ffms2.Source(source=src.path, cache=False, threads=int(-1))
        dst_data = core.ffms2.Source(source=self.path, cache=False, threads=int(-1))

        src_data = src_data.resize.Bicubic(format=vs.RGBS, matrix_in_s="709")
        dst_data = dst_data.resize.Bicubic(format=vs.RGBS, matrix_in_s="709")

        if e > 1:
            src_data = src_data.std.SelectEvery(cycle=e, offsets=0)
            dst_data = dst_data.std.SelectEvery(cycle=e, offsets=0)

        ssimu2_obj = src_data.vszip.Metrics(dst_data, [0])

        ssimu2_list: list[float] = []
        with tqdm(
            total=ssimu2_obj.num_frames,
            desc="Calculating SSIMULACRA2 scores",
            unit=" frame",
            colour="blue",
        ) as pbar:
            for i, f in enumerate(ssimu2_obj.frames()):
                ssimu2_list.append(f.props["_SSIMULACRA2"])
                pbar.update(1)
                if not i % 24:
                    (average, harmonic_mean, std_dev, percentile_10th) = (
                        calc_some_scores(ssimu2_list)
                    )
                    pbar.set_postfix(
                        {
                            "avg": f"{average:.2f}",
                        }
                    )

        self.ssimu2_avg, self.ssimu2_hmn, self.ssimu2_sdv, self.ssimu2_p10 = (
            calc_some_scores(ssimu2_list)
        )

    def calculate_butteraugli(self, src: SrcVideo, e: int) -> None:
        """
        Calculate Butteraugli score between a source video & a distorted video.
        """
        core = vs.core

        src_data = core.ffms2.Source(source=src.path, cache=False, threads=int(-1))
        dst_data = core.ffms2.Source(source=self.path, cache=False, threads=int(-1))

        src_data = src_data.resize.Bicubic(format=vs.RGBS, matrix_in_s="709")
        dst_data = dst_data.resize.Bicubic(format=vs.RGBS, matrix_in_s="709")

        if e > 1:
            src_data = src_data.std.SelectEvery(cycle=e, offsets=0)
            dst_data = dst_data.std.SelectEvery(cycle=e, offsets=0)

        butter_obj = src_data.julek.Butteraugli(dst_data, [0])

        butter_list: list[float] = []
        with tqdm(
            total=butter_obj.num_frames,
            desc="Calculating Butteraugli scores",
            unit=" frame",
            colour="yellow",
        ) as pbar:
            for i, f in enumerate(butter_obj.frames()):
                butter_list.append(f.props["_FrameButteraugli"])
                pbar.update(1)
                if not i % 24:
                    (average, harmonic_mean, std_dev, percentile_10th) = (
                        calc_some_scores(butter_list)
                    )
                    pbar.set_postfix(
                        {
                            "avg": f"{average:.2f}",
                        }
                    )

        self.butter_avg, self.butter_hmn, self.butter_sdv, self.butter_p10 = (
            calc_some_scores(butter_list)
        )

    def calculate_xpsnr(self, src: SrcVideo) -> None:
        """
        Calculate XPSNR scores between a source video & a distorted video using FFmpeg.
        """

        cmd: list[str] = [
            "ffmpeg",
            "-i",
            self.path,
            "-i",
            src.path,
            "-hide_banner",
            "-lavfi",
            "xpsnr=shortest=1",
            "-f",
            "null",
            "-",
        ]

        process: Popen[str] = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
        )

        _, stderr = process.communicate()

        # Parse XPSNR scores using regex
        rgx: str = r"XPSNR\s+y:\s*(\d+\.\d+)\s+u:\s*(\d+\.\d+)\s+v:\s*(\d+\.\d+)"
        match = re.search(rgx, stderr)
        if match:
            self.xpsnr_y = float(match.group(1))
            self.xpsnr_u = float(match.group(2))
            self.xpsnr_v = float(match.group(3))
        else:
            self.xpsnr_y = 0.0
            self.xpsnr_u = 0.0
            self.xpsnr_v = 0.0

        maxval: int = 255
        xpsnr_mse_y: float = psnr_to_mse(self.xpsnr_y, maxval)
        xpsnr_mse_u: float = psnr_to_mse(self.xpsnr_u, maxval)
        xpsnr_mse_v: float = psnr_to_mse(self.xpsnr_v, maxval)
        w_xpsnr_mse: float = ((4.0 * xpsnr_mse_y) + xpsnr_mse_u + xpsnr_mse_v) / 6.0
        self.w_xpsnr = 10.0 * math.log10((maxval**2) / w_xpsnr_mse)


def psnr_to_mse(p: float, m: int) -> float:
    """
    Convert PSNR to MSE (Mean Squared Error). Used in weighted XPSNR calculation.
    """
    return (m**2) / (10 ** (p / 10))


def calc_some_scores(score_list: list[float]) -> tuple[float, float, float, float]:
    """
    Calculate the average, harmonic mean, standard deviation, & 10th percentile of a list of scores.
    """
    average: float = sum(score_list) / len(score_list)
    positive_scores: list[float] = [score for score in score_list if score > 0.0]
    negative_scores: list[float] = [score for score in score_list if score <= 0.0]
    if positive_scores:
        list_of_pos_reciprocals: list[float] = [1 / score for score in positive_scores]
        list_of_neg_reciprocals: list[float] = [1 / score for score in negative_scores]
        sum_reciprocals: float = sum(list_of_pos_reciprocals) - sum(
            list_of_neg_reciprocals
        )
        harmonic_mean: float = len(positive_scores) / sum_reciprocals
    else:
        harmonic_mean: float = 0.0
    std_dev: float = (
        sum((x - average) ** 2 for x in score_list) / len(score_list)
    ) ** 0.5
    percentile_10th: float = sorted(score_list)[int(len(score_list) * 0.1)]
    return (average, harmonic_mean, std_dev, percentile_10th)


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

    src: SrcVideo = SrcVideo(args.source)
    dst: DstVideo = DstVideo(args.distorted)

    print(f"Source video:    \033[4m{src.name}\033[0m")
    print(f"Distorted video: \033[4m{dst.name}\033[0m")

    # Calculate SSIMULACRA2 scores
    print("Running \033[94mSSIMULACRA2\033[0m ...")
    dst.calculate_ssimulacra2(src, every)
    print(f"\033[94mSSIMULACRA2\033[0m scores for every \033[95m{every}\033[0m frame:")
    print(f" Average:       \033[1m{dst.ssimu2_avg:.5f}\033[0m")
    print(f" Harmonic Mean: \033[1m{dst.ssimu2_hmn:.5f}\033[0m")
    print(f" Std Deviation: \033[1m{dst.ssimu2_sdv:.5f}\033[0m")
    print(f" 10th Pctile:   \033[1m{dst.ssimu2_p10:.5f}\033[0m")

    # Calculate Butteraugli scores
    print("Running \033[93mButteraugli\033[0m ...")
    dst.calculate_butteraugli(src, every)
    print(f"\033[93mButteraugli\033[0m scores for every \033[95m{every}\033[0m frame:")
    print(f" Average:       \033[1m{dst.butter_avg:.5f}\033[0m")
    print(f" Harmonic Mean: \033[1m{dst.butter_hmn:.5f}\033[0m")
    print(f" Std Deviation: \033[1m{dst.butter_sdv:.5f}\033[0m")
    print(f" 10th Pctile:   \033[1m{dst.butter_p10:.5f}\033[0m")

    # Calculate XPSNR scores
    print("Running \033[91mXPSNR\033[0m ...")
    dst.calculate_xpsnr(src)
    print("\033[91mXPSNR\033[0m scores:")
    print(f" XPSNR Y: \033[1m{dst.xpsnr_y:.5f}\033[0m")
    print(f" XPSNR U: \033[1m{dst.xpsnr_u:.5f}\033[0m")
    print(f" XPSNR V: \033[1m{dst.xpsnr_v:.5f}\033[0m")
    print(f" W-XPSNR: \033[1m{dst.w_xpsnr:.5f}\033[0m")


if __name__ == "__main__":
    main()
