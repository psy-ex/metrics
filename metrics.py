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
import os
from argparse import Namespace

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
    ssimu2_avg: float
    ssimu2_hmn: float
    ssimu2_sdv: float
    ssimu2_p10: float

    def __init__(self, pth: str) -> None:
        self.path = pth
        self.name = os.path.basename(pth)
        self.ssimu2_avg = 0.0
        self.ssimu2_hmn = 0.0
        self.ssimu2_sdv = 0.0
        self.ssimu2_p10 = 0.0

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
                            "harmean": f"{harmonic_mean:.2f}",
                            "std": f"{std_dev:.2f}",
                            "p10": f"{percentile_10th:.2f}",
                        }
                    )

        self.ssimu2_avg, self.ssimu2_hmn, self.ssimu2_sdv, self.ssimu2_p10 = (
            calc_some_scores(ssimu2_list)
        )


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
    print(
        f"Running \033[94mSSIMULACRA2\033[0m on source \033[92m{src.name}\033[0m & distorted \033[93m{dst.name}\033[0m ..."
    )
    dst.calculate_ssimulacra2(src, every)
    print(
        f"\033[94mSSIMULACRA2\033[0m scores for \033[92m{src.name}\033[0m & \033[93m{dst.name}\033[0m (every \033[95m{every}\033[0m frame):"
    )
    print(f" Average:       \033[1m{dst.ssimu2_avg:.5f}\033[0m")
    print(f" Harmonic Mean: \033[1m{dst.ssimu2_hmn:.5f}\033[0m")
    print(f" Std Deviation: \033[1m{dst.ssimu2_sdv:.5f}\033[0m")
    print(f" 10th Pctile:   \033[1m{dst.ssimu2_p10:.5f}\033[0m")


if __name__ == "__main__":
    main()
