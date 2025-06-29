import math
import os
import re
import statistics
import subprocess
import time
from subprocess import Popen

import vapoursynth as vs
from tqdm import tqdm
from vapoursynth import VideoNode
from vstools import initialize_clip


class CoreVideo:
    """
    Source video class.
    """

    path: str
    name: str
    size: int
    e: int
    threads: int
    gpu_streams: int

    video_width: int
    video_height: int

    # VapourSynth video object
    video: VideoNode

    def __init__(self, pth: str, e: int, t: int, g: int) -> None:
        self.path = pth
        self.name = os.path.basename(pth)
        self.size = self.get_input_filesize()
        self.e = e
        self.threads = t
        self.gpu_streams = g
        self.video = self.vapoursynth_init()
        self.video_width, self.video_height = self.get_video_dimensions()

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
        print(
            f"Using {self.threads} {'GPU' if self.gpu_streams else 'CPU'} threads for {'SSIMULACRA2 & Butteraugli' if self.gpu_streams else 'SSIMULACRA2'}"
        )
        if self.gpu_streams:
            print(f"Using {self.gpu_streams} GPU streams for SSIMULACRA2 & Butteraugli")
        core.num_threads = self.threads
        video = core.ffms2.Source(source=self.path, cache=False, threads=self.threads)
        video = initialize_clip(video, bits=0)
        video = video.resize.Bicubic(format=vs.RGBS)
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

    # VMAF scores
    vmaf: float
    vmaf_neg_hmn: float

    # SSIM score
    ssim: float

    # PSNR score
    psnr: float

    # Average VMAF, SSIM, PSNR
    svt_triple: float

    def __init__(self, pth: str, e: int, t: int, g: int) -> None:
        self.path = pth
        self.name = os.path.basename(pth)
        self.size = self.get_input_filesize()
        self.e = e
        self.video_width, self.video_height = self.get_video_dimensions()
        self.threads = t
        self.gpu_streams = g
        self.video = self.vapoursynth_init()
        self.ssimu2_avg = 0.0
        self.ssimu2_sdv = 0.0
        self.ssimu2_p10 = 0.0
        self.butter_dis = 0.0
        self.butter_mds = 0.0
        self.xpsnr_y = 0.0
        self.xpsnr_u = 0.0
        self.xpsnr_v = 0.0
        self.w_xpsnr = 0.0
        self.vmaf = 0.0
        self.vmaf_neg_hmn = 0.0
        self.ssim = 0.0
        self.psnr = 0.0
        self.svt_triple = 0.0

    def calculate_ssimulacra2(self, src: CoreVideo) -> None:
        """
        Calculate SSIMULACRA2 score between a source video & a distorted video.
        """

        if self.gpu_streams:
            ssimu2_obj = src.video.vship.SSIMULACRA2(
                self.video, numStream=self.gpu_streams
            )
        else:
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

        self.ssimu2_avg, self.ssimu2_sdv, self.ssimu2_p10 = calc_some_scores(
            ssimu2_list
        )

    def calculate_butteraugli(
        self,
        src: CoreVideo,
    ) -> None:
        """
        Calculate Butteraugli score between a source video & a distorted video.
        """

        if self.gpu_streams:
            butter_obj = src.video.vship.BUTTERAUGLI(
                self.video, numStream=self.gpu_streams
            )
        else:
            print("Skipping Butteraugli, no GPU threads available (set with -g)")
            self.butter_dis = 0.0
            self.butter_mds = 0.0
            return

        butter_distance_list: list[float] = []
        with tqdm(
            total=butter_obj.num_frames,
            desc="Calculating Butteraugli scores",
            unit=" frame",
            colour="yellow",
        ) as pbar:
            for i, f in enumerate(butter_obj.frames()):
                d: float = f.props["_BUTTERAUGLI_3Norm"]
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

    def calculate_ffmpeg_metrics(self, src: CoreVideo) -> None:
        """
        Calculate XPSNR, SSIM, PSNR, VMAF & VMAF-NEG scores between a source
        video & a distorted video with FFmpeg.
        """

        filtergraph: str = (
            "[0:v]split=5[dst0][dst1][dst2][dst3][dst4];"
            "[1:v]split=5[src0][src1][src2][src3][src4];"
            "[dst0][src0]ssim;"
            "[dst1][src1]psnr;"
            "[src2][dst2]xpsnr=shortest=1;"
            f"[dst3][src3]libvmaf=model='version=vmaf_v0.6.1':n_threads={self.threads}:n_subsample={self.e};"
            f"[dst4][src4]libvmaf=model='version=vmaf_v0.6.1neg':n_threads={self.threads}:n_subsample={self.e}:pool=harmonic_mean"
        )

        cmd: list[str] = [
            "ffmpeg",
            "-threads",
            str(self.threads),
            "-hide_banner",
            "-i",
            self.path,
            "-i",
            src.path,
            "-lavfi",
            filtergraph,
            "-f",
            "null",
            "-",
        ]

        print("Calculating XPSNR, SSIM, PSNR, VMAF & VMAF-NEG scores...")
        process: Popen[str] = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            text=True,
        )
        _, stderr_output = process.communicate()

        ssim_match = re.search(
            r"\[Parsed_ssim_2\s*@\s*.*?\]\s*SSIM.*?All:(\d+\.\d+)",
            stderr_output,
        )
        if ssim_match:
            self.ssim = float(ssim_match.group(1)) * 100

        psnr_match = re.search(
            r"\[Parsed_psnr_3\s*@\s*.*?\]\s*PSNR\s+y:([\d\.]+)\s+u:([\d\.]+)\s+v:([\d\.]+)\s+average:([\d\.]+)\s+min:([\d\.]+)\s+max:([\d\.]+)",
            stderr_output,
        )
        if psnr_match:
            self.psnr = float(psnr_match.group(4))

        xpsnr_match = re.search(
            r"\[Parsed_xpsnr_4\s*@\s*.*?\]\s*XPSNR\s+y:\s*(\d+\.\d+)\s+u:\s*(\d+\.\d+)\s+v:\s*(\d+\.\d+)",
            stderr_output,
        )
        if xpsnr_match:
            self.xpsnr_y = float(xpsnr_match.group(1))
            self.xpsnr_u = float(xpsnr_match.group(2))
            self.xpsnr_v = float(xpsnr_match.group(3))

        maxval: int = 255
        xpsnr_mse_y: float = psnr_to_mse(self.xpsnr_y, maxval)
        xpsnr_mse_u: float = psnr_to_mse(self.xpsnr_u, maxval)
        xpsnr_mse_v: float = psnr_to_mse(self.xpsnr_v, maxval)
        w_xpsnr_mse: float = ((4.0 * xpsnr_mse_y) + xpsnr_mse_u + xpsnr_mse_v) / 6.0
        self.w_xpsnr = 10.0 * math.log10((maxval**2) / w_xpsnr_mse)

        vmaf_score_pattern = (
            r"\[Parsed_libvmaf_([56])\s*@\s*.*?\]\s*VMAF score:\s*(\d+\.\d+)"
        )
        all_vmaf_matches: list[str] = re.findall(vmaf_score_pattern, stderr_output)
        for filter_idx, score_str in all_vmaf_matches:
            score = float(score_str)
            match filter_idx:
                case "5":
                    self.vmaf = score
                case "6":
                    self.vmaf_neg_hmn = score

        self.svt_triple = statistics.mean([self.vmaf, self.ssim, self.psnr])

    def print_ssimulacra2(self) -> None:
        """
        Print SSIMULACRA2 scores.
        """
        print(
            f"\033[94mSSIMULACRA2\033[0m scores for every \033[95m{self.e}\033[0m frame:"
        )
        print(f" Average:       \033[1m{self.ssimu2_avg:.5f}\033[0m")
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

    def print_ffmpeg_metrics(self) -> None:
        """
        Print XPSNR, SSIM, PSNR, VMAF & VMAF-NEG scores.
        """
        print("\033[91mXPSNR\033[0m scores:")
        print(f" XPSNR:         \033[1m{self.xpsnr_y:.5f}\033[0m")
        print(f" W-XPSNR:       \033[1m{self.w_xpsnr:.5f}\033[0m")
        print(
            f"\033[38;5;208mVMAF\033[0m scores for every \033[95m{self.e}\033[0m frame:"
        )
        print(f" VMAF NEG:      \033[1m{self.vmaf_neg_hmn:.5f}\033[0m")
        print(f" VMAF:          \033[1m{self.vmaf:.5f}\033[0m")
        print(f"SSIM Score:     \033[1m{self.ssim:.5f}\033[0m")
        print(f"PSNR Score:     \033[1m{self.psnr:.5f}\033[0m")
        print("AVG VMAF/SSIM/PSNR score:")
        print(f"                \033[1m{self.svt_triple:.5f}\033[0m")


class VideoEnc:
    """
    Video encoding class, containing encoder commands.
    """

    src: CoreVideo
    dst_pth: str
    q: int
    encoder: str
    encoder_args: list[str]
    enc_cmd: list[str]
    time: float

    def __init__(
        self,
        src: CoreVideo,
        q: int,
        encoder: str,
        encoder_args: list[str],
        dst_pth: str = "",
    ) -> None:
        self.src = src
        self.dst_pth = dst_pth
        self.q = q
        self.encoder = encoder
        self.encoder_args = encoder_args if encoder_args else [""]
        self.enc_cmd = self.set_enc_cmd()
        self.time = 0

    def set_enc_cmd(self) -> list[str]:
        p: str = os.path.splitext(os.path.basename(self.src.path))[0]
        if not self.dst_pth:
            match self.encoder:
                case "x264":
                    self.dst_pth = f"./{p}_{self.encoder}_q{self.q}.264"
                case "x265":
                    self.dst_pth = f"./{p}_{self.encoder}_q{self.q}.265"
                case "vvenc":
                    self.dst_pth = f"./{p}_{self.encoder}_q{self.q}.266"
                case _:
                    self.dst_pth = f"./{p}_{self.encoder}_q{self.q}.ivf"
        else:
            match self.encoder:
                case "x264":
                    self.dst_pth = self.dst_pth + ".264"
                case "x265":
                    self.dst_pth = self.dst_pth + ".265"
                case "vvenc":
                    self.dst_pth = self.dst_pth + ".266"
                case _:
                    self.dst_pth = self.dst_pth + ".ivf"

        match self.encoder:
            case "x264":
                cmd: list[str] = [
                    "x264",
                    "--demuxer",
                    "y4m",
                    "--crf",
                    f"{self.q}",
                    "-o",
                    f"{self.dst_pth}",
                    "-",
                ]
            case "x265":
                cmd: list[str] = [
                    "x265",
                    "--y4m",
                    "-",
                    "--crf",
                    f"{self.q}",
                    "-o",
                    f"{self.dst_pth}",
                ]
            case "vvenc":
                cmd: list[str] = [
                    "vvencapp",
                    "--y4m",
                    "-i",
                    "-",
                    "--qp",
                    f"{self.q}",
                    "-o",
                    f"{self.dst_pth}",
                ]
            case "svtav1":
                cmd: list[str] = [
                    "SvtAv1EncApp",
                    "-i",
                    "-",
                    "-b",
                    f"{self.dst_pth}",
                    "--crf",
                    f"{self.q}",
                ]
            case _:  # "aomenc":
                cmd: list[str] = [
                    "aomenc",
                    "--ivf",
                    "--end-usage=q",
                    f"--cq-level={self.q}",
                    "--passes=1",
                    "-y",
                    "-",
                    "-o",
                    f"{self.dst_pth}",
                ]

        if self.encoder_args != [""]:
            cmd.extend(self.encoder_args)
        print(" ".join(cmd))
        return cmd

    def encode(self, e: int, t: int, g: int) -> DstVideo:
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
            f"{self.src.path}",
            "-pix_fmt",
            "yuv420p10le",
            "-strict",
            "-2",
            "-f",
            "yuv4mpegpipe",
            "-",
        ]
        print(
            f"Encoding {self.src.name} at Q{self.q} with {self.encoder} ({self.src.path} --> {self.dst_pth})"
        )
        ff_proc: Popen[bytes] = subprocess.Popen(
            ff_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        start_time: float = time.time()
        enc_proc: Popen[str] = subprocess.Popen(
            self.enc_cmd,
            stdin=ff_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        _, stderr = enc_proc.communicate()
        encode_time: float = time.time() - start_time
        self.time = encode_time
        print(stderr)
        return DstVideo(self.dst_pth, e, t, g)

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


def calc_some_scores(score_list: list[float]) -> tuple[float, float, float]:
    """
    Calculate the average, standard deviation, & 10th percentile of a list of scores.
    """
    average: float = statistics.mean(score_list)
    std_dev: float = statistics.stdev(score_list)
    percentile_10th: float = statistics.quantiles(score_list, n=100)[10]
    return (average, std_dev, percentile_10th)
