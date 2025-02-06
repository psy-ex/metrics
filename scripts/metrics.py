import math
import os
import re
import statistics
import subprocess
from subprocess import Popen

import vapoursynth as vs
from tqdm import tqdm
from vapoursynth import VideoNode


class CoreVideo:
    """
    Source video class.
    """

    path: str
    name: str
    size: int
    e: int

    video_width: int
    video_height: int

    # VapourSynth video object
    video: VideoNode

    def __init__(self, pth: str, e: int) -> None:
        self.path = pth
        self.name = os.path.basename(pth)
        self.size = self.get_input_filesize()
        self.e = e
        self.video = self.vapoursynth_init()

    def get_input_filesize(self) -> int:
        """
        Get the input file size of the distorted video.
        """
        return os.path.getsize(self.path)

    def vapoursynth_init(self) -> VideoNode:
        """
        Initialize VapourSynth video object for the distorted video.
        """
        core = vs.core
        video = core.ffms2.Source(source=self.path, cache=False, threads=int(-1))
        video = video.resize.Bicubic(format=vs.RGBS, matrix_in_s="709")
        if self.e > 1:
            video = video.std.SelectEvery(cycle=self.e, offsets=0)
        return video

    def get_video_dimensions(self) -> tuple[int, int]:
        """
        Get the width & height of the distorted video.
        """
        core = vs.core
        src_data = core.ffms2.Source(source=self.path, cache=False, threads=int(-1))
        return (src_data.width, src_data.height)


class DstVideo(CoreVideo):
    """
    Distorted video class containing metric scores.
    """

    # SSIMULACRA2 scores
    ssimu2_avg: float
    ssimu2_hmn: float
    ssimu2_sdv: float
    ssimu2_p10: float

    # Butteraugli scores
    butter_dis: float
    butter_mds: float

    # XPSNR scores
    xpsnr_y: float
    xpsnr_u: float
    xpsnr_v: float
    w_xpsnr: float

    def __init__(self, pth: str, e: int) -> None:
        self.path = pth
        self.name = os.path.basename(pth)
        self.size = self.get_input_filesize()
        self.e = e
        self.video_width, self.video_height = self.get_video_dimensions()
        self.video = self.vapoursynth_init()
        self.ssimu2_avg = 0.0
        self.ssimu2_hmn = 0.0
        self.ssimu2_sdv = 0.0
        self.ssimu2_p10 = 0.0
        self.butter_dis = 0.0
        self.butter_mds = 0.0
        self.xpsnr_y = 0.0
        self.xpsnr_u = 0.0
        self.xpsnr_v = 0.0
        self.w_xpsnr = 0.0

    def calculate_ssimulacra2(self, src: CoreVideo) -> None:
        """
        Calculate SSIMULACRA2 score between a source video & a distorted video.
        """

        ssimu2_obj = src.video.vszip.Metrics(self.video, [0])

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
                    avg: float = sum(ssimu2_list) / len(ssimu2_list)
                    pbar.set_postfix(
                        {
                            "avg": f"{avg:.2f}",
                        }
                    )

        self.ssimu2_avg, self.ssimu2_hmn, self.ssimu2_sdv, self.ssimu2_p10 = (
            calc_some_scores(ssimu2_list)
        )

    def calculate_butteraugli(
        self,
        src: CoreVideo,
    ) -> None:
        """
        Calculate Butteraugli score between a source video & a distorted video.
        """

        butter_obj = src.video.julek.Butteraugli(self.video, [0])

        butter_distance_list: list[float] = []
        with tqdm(
            total=butter_obj.num_frames,
            desc="Calculating Butteraugli scores",
            unit=" frame",
            colour="yellow",
        ) as pbar:
            for i, f in enumerate(butter_obj.frames()):
                d: float = f.props["_FrameButteraugli"]
                butter_distance_list.append(d)
                pbar.update(1)
                if not i % 24:
                    dis: float = sum(butter_distance_list) / len(butter_distance_list)
                    pbar.set_postfix(
                        {
                            "dis": f"{dis:.2f}",
                        }
                    )

        self.butter_dis = sum(butter_distance_list) / len(butter_distance_list)
        self.butter_mds = max(butter_distance_list)

    def calculate_xpsnr(self, src: CoreVideo) -> None:
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

        print("Calculating XPSNR scores...")
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

    def print_ssimulacra2(self) -> None:
        """
        Print SSIMULACRA2 scores.
        """
        print(
            f"\033[94mSSIMULACRA2\033[0m scores for every \033[95m{self.e}\033[0m frame:"
        )
        print(f" Average:       \033[1m{self.ssimu2_avg:.5f}\033[0m")
        print(f" Harmonic Mean: \033[1m{self.ssimu2_hmn:.5f}\033[0m")
        print(f" Std Deviation: \033[1m{self.ssimu2_sdv:.5f}\033[0m")
        print(f" 10th Pctile:   \033[1m{self.ssimu2_p10:.5f}\033[0m")

    def print_butteraugli(self) -> None:
        """
        Print Butteraugli scores.
        """
        print(
            f"\033[93mButteraugli\033[0m scores for every \033[95m{self.e}\033[0m frame:"
        )
        print(f" Distance:      \033[1m{self.butter_dis:.5f}\033[0m")
        print(f" Max Distance:  \033[1m{self.butter_mds:.5f}\033[0m")

    def print_xpsnr(self) -> None:
        """
        Print XPSNR scores.
        """
        print("\033[91mXPSNR\033[0m scores:")
        print(f" XPSNR Y:       \033[1m{self.xpsnr_y:.5f}\033[0m")
        print(f" XPSNR U:       \033[1m{self.xpsnr_u:.5f}\033[0m")
        print(f" XPSNR V:       \033[1m{self.xpsnr_v:.5f}\033[0m")
        print(f" W-XPSNR:       \033[1m{self.w_xpsnr:.5f}\033[0m")


class VideoEnc:
    """
    Video encoding class, containing encoder commands.
    """

    enc_cmd: list[str]
    src_pth: str
    dst_pth: str
    q: int
    encoder: str
    encoder_args: list[str]

    def __init__(
        self,
        src_pth: str,
        q: int,
        encoder: str,
        encoder_args: list[str],
        dst_pth: str = "",
    ) -> None:
        self.enc_cmd = []
        self.src_pth = src_pth
        self.dst_pth = dst_pth
        self.q = q
        self.encoder = encoder
        self.encoder_args = encoder_args if encoder_args else [""]
        self.enc_cmd = self.set_enc_cmd()

    def set_enc_cmd(self) -> list[str]:
        p: str = os.path.splitext(os.path.basename(self.src_pth))[0]
        if not self.dst_pth:
            self.dst_pth = f"./{p}_{self.encoder}_q{self.q}.ivf"
        print(f"Selected encoder: {self.encoder}")
        print(f"Encoding {self.src_pth} to {self.dst_pth} ...")
        cmd: list[str] = [
            "SvtAv1EncApp",
            "-i",
            "-",
            "-b",
            f"{self.dst_pth}",
            "--crf",
            f"{self.q}",
        ]
        if self.encoder_args != [""]:
            cmd.extend(self.encoder_args)
        print(" ".join(cmd))
        return cmd

    def encode(self) -> str:
        """
        Encode the video using FFmpeg piped to your chosen encoder.
        """
        ff_cmd: list[str] = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-loglevel",
            "error",
            "-i",
            f"{self.src_pth}",
            "-pix_fmt",
            "yuv420p10le",
            "-strict",
            "-2",
            "-f",
            "yuv4mpegpipe",
            "-",
        ]
        print(f"Encoding video at Q{self.q} with {self.encoder} ...")
        ff_proc: Popen[bytes] = subprocess.Popen(
            ff_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        enc_proc: Popen[str] = subprocess.Popen(
            self.enc_cmd,
            stdin=ff_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        _, stderr = enc_proc.communicate()
        print(stderr)
        return self.dst_pth

    def remove_output(self) -> None:
        """
        Remove the output file.
        """
        os.remove(self.dst_pth)


def psnr_to_mse(p: float, m: int) -> float:
    """
    Convert PSNR to MSE (Mean Squared Error). Used in weighted XPSNR calculation.
    """
    return (m**2) / (10 ** (p / 10))


def calc_some_scores(score_list: list[float]) -> tuple[float, float, float, float]:
    """
    Calculate the average, harmonic mean, standard deviation, & 10th percentile of a list of scores.
    """
    average: float = statistics.mean(score_list)
    std_dev: float = statistics.stdev(score_list)
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
    percentile_10th: float = statistics.quantiles(score_list, n=100)[10]
    return (average, harmonic_mean, std_dev, percentile_10th)
