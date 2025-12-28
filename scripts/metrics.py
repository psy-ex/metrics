import math
import os
import re
import statistics
import subprocess
import time
from subprocess import Popen
import shlex

from tqdm import tqdm


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

    def __init__(self, pth: str, e: int, t: int, g: int) -> None:
        self.path = pth
        self.name = os.path.basename(pth)
        self.size = self.get_input_filesize()
        self.e = e
        self.threads = t
        self.gpu_streams = g
        self.video_width, self.video_height = self.get_video_dimensions()

    def get_input_filesize(self) -> int:
        """
        Get the filesize of the input video in bytes.
        """
        return os.path.getsize(self.path)

    def get_video_dimensions(self) -> tuple[int, int]:
        """
        Get the width & height of the video using ffprobe.
        """
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=s=x:p=0",
            self.path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            dimensions = result.stdout.strip().split("x")
            if len(dimensions) == 2:
                return int(dimensions[0]), int(dimensions[1])
        except Exception:
            pass
        return 0, 0


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

    # CVVDP scores
    cvvdp_avg: float
    cvvdp_sdv: float
    cvvdp_p10: float

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
        super().__init__(pth, e, t, g)
        self.ssimu2_avg = 0.0
        self.ssimu2_sdv = 0.0
        self.ssimu2_p10 = 0.0
        self.butter_dis = 0.0
        self.butter_mds = 0.0
        self.cvvdp_avg = 0.0
        self.cvvdp_sdv = 0.0
        self.cvvdp_p10 = 0.0
        self.xpsnr_y = 0.0
        self.xpsnr_u = 0.0
        self.xpsnr_v = 0.0
        self.w_xpsnr = 0.0
        self.vmaf = 0.0
        self.vmaf_neg_hmn = 0.0
        self.ssim = 0.0
        self.psnr = 0.0
        self.svt_triple = 0.0

    def _run_ffvship(
        self, src: CoreVideo, metric: str, extra_args: list[str] | None = None
    ) -> list[float]:
        """
        Run FFVship for a specific metric and return a list of per-frame scores.
        """
        cmd = [
            "FFVship",
            "-s",
            src.path,
            "-e",
            self.path,
            "-m",
            metric,
            "-g",
            str(self.gpu_streams),
            "-t",
            str(self.threads),
            "--every",
            str(self.e),
            "--live-score-output",
        ]
        if extra_args:
            cmd.extend(extra_args)

        scores: list[float] = []

        # Try to get frame count for tqdm
        total_frames = 0
        ffprobe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_frames",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            src.path,
        ]
        try:
            res = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
            total_frames = int(res.stdout.strip()) // self.e
        except Exception:
            total_frames = 0

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        desc_map = {
            "SSIMULACRA2": "Calculating SSIMULACRA2 scores",
            "Butteraugli": "Calculating Butteraugli scores",
            "CVVDP": "Calculating CVVDP scores",
        }
        color_map = {
            "SSIMULACRA2": "blue",
            "Butteraugli": "yellow",
            "CVVDP": "green",
        }

        with tqdm(
            total=total_frames if total_frames > 0 else None,
            desc=desc_map.get(metric, f"Calculating {metric} scores"),
            unit=" frame",
            colour=color_map.get(metric, "white"),
        ) as pbar:
            if process.stdout:
                for line in process.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        parts = line.split()
                        if len(parts) == 2:
                            score = float(parts[1])
                            scores.append(score)
                            pbar.update(1)
                            if len(scores) % 24 == 0:
                                avg = sum(scores) / len(scores)
                                pbar.set_postfix({"avg": f"{avg:.2f}"})
                    except ValueError:
                        pass
        process.wait()
        return scores

    def calculate_ssimulacra2(self, src: CoreVideo) -> None:
        """
        Calculate SSIMULACRA2 score between a source video & a distorted video using FFVship.
        """
        scores = self._run_ffvship(src, "SSIMULACRA2")
        if scores:
            self.ssimu2_avg, self.ssimu2_sdv, self.ssimu2_p10 = calc_some_scores(scores)

    def calculate_butteraugli(self, src: CoreVideo) -> None:
        """
        Calculate Butteraugli score between a source video & a distorted video using FFVship.
        """
        # Use --qnorm 3 to match previous behavior (3pnorm)
        scores = self._run_ffvship(src, "Butteraugli", ["--qnorm", "3"])
        if scores:
            self.butter_dis = sum(scores) / len(scores)
            self.butter_mds = max(scores)

    def calculate_cvvdp(self, src: CoreVideo) -> None:
        """
        Calculate CVVDP score between a source video & a distorted video using FFVship.
        """
        scores = self._run_ffvship(src, "CVVDP")
        if scores:
            self.cvvdp_avg, self.cvvdp_sdv, self.cvvdp_p10 = calc_some_scores(scores)

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
            "[dst2][src2]xpsnr=shortest=1;"
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
        print(f"SSIMULACRA2 Average:       \033[1m{self.ssimu2_avg:.5f}\033[0m")
        print(f"SSIMULACRA2 Std Dev:       {self.ssimu2_sdv:.5f}")
        print(f"SSIMULACRA2 10th %:        {self.ssimu2_p10:.5f}")

    def print_butteraugli(self) -> None:
        """
        Print Butteraugli scores.
        """
        print(f"Butteraugli Distance:      \033[1m{self.butter_dis:.5f}\033[0m")
        print(f"Butteraugli Max Distance:  {self.butter_mds:.5f}")

    def print_cvvdp(self) -> None:
        """
        Print CVVDP scores.
        """
        print(f"CVVDP Average:             \033[1m{self.cvvdp_avg:.5f}\033[0m")
        print(f"CVVDP Std Dev:             {self.cvvdp_sdv:.5f}")
        print(f"CVVDP 10th %:              {self.cvvdp_p10:.5f}")

    def print_ffmpeg_metrics(self) -> None:
        """
        Print XPSNR, SSIM, PSNR, VMAF & VMAF-NEG scores.
        """
        print(f"W-XPSNR:                   \033[1m{self.w_xpsnr:.5f}\033[0m")
        print(f"VMAF NEG (Harmonic Mean):  \033[1m{self.vmaf_neg_hmn:.5f}\033[0m")
        print(f"VMAF:                      \033[1m{self.vmaf:.5f}\033[0m")
        print(f"SSIM:                      \033[1m{self.ssim:.5f}\033[0m")
        print(f"PSNR:                      \033[1m{self.psnr:.5f}\033[0m")
        print(f"SVT Triple:                \033[1m{self.svt_triple:.5f}\033[0m")


class VideoEnc:
    """
    Video encoder class.
    """

    src: CoreVideo
    q: int
    enc: str
    enc_args: list[str]
    dst_pth: str
    time: float

    def __init__(
        self,
        src: CoreVideo,
        q: int,
        enc: str,
        enc_args: list[str],
        dst_pth: str | None = None,
    ) -> None:
        self.src = src
        self.q = q
        self.enc = enc
        self.enc_args = enc_args
        if dst_pth:
            self.dst_pth = dst_pth
        else:
            ext = {
                "x264": "mp4",
                "x265": "mp4",
                "svtav1": "ivf",
                "aomenc": "ivf",
                "vpxenc": "webm",
            }.get(enc, "mp4")
            self.dst_pth = f"{os.path.splitext(src.name)[0]}_{q}.{ext}"

    def set_enc_cmd(self) -> list[str]:
        """
        Set the encoder command based on the encoder choice.
        """
        cmd: list[str] = []
        if self.enc == "x264":
            cmd = (
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    self.src.path,
                    "-an",
                    "-c:v",
                    "libx264",
                    "-crf",
                    str(self.q),
                ]
                + self.enc_args
                + [self.dst_pth]
            )
        elif self.enc == "x265":
            cmd = (
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    self.src.path,
                    "-an",
                    "-c:v",
                    "libx265",
                    "-crf",
                    str(self.q),
                ]
                + self.enc_args
                + [self.dst_pth]
            )
        elif self.enc == "svtav1":
            # SvtAv1EncApp only accepts y4m input; use a shell pipeline:
            # ffmpeg (to y4m) | SvtAv1EncApp -i - -b - | ffmpeg -i - -c copy <dst>
            enc_args_str = " ".join(shlex.quote(arg) for arg in self.enc_args) if self.enc_args else ""
            ffmpeg_in = f'ffmpeg -hide_banner -loglevel error -i {shlex.quote(self.src.path)} -an -pix_fmt yuv420p10le -strict -2 -f yuv4mpegpipe -'
            svt_cmd = f'SvtAv1EncApp -i - --rc 0 --crf {shlex.quote(str(self.q))} -b - {enc_args_str} --progress 3'
            ffmpeg_out = f'ffmpeg -y -hide_banner -loglevel error -i - -c copy {shlex.quote(self.dst_pth)}'
            # Return a shell string pipeline; encode() will run it with shell=True
            cmd = f"{ffmpeg_in} | {svt_cmd} | {ffmpeg_out}"
        elif self.enc == "aomenc":
            cmd = (
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    self.src.path,
                    "-an",
                    "-c:v",
                    "libaom-av1",
                    "-crf",
                    str(self.q),
                    "-b:v",
                    "0",
                ]
                + self.enc_args
                + [self.dst_pth]
            )
        elif self.enc == "vpxenc":
            cmd = (
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    self.src.path,
                    "-an",
                    "-c:v",
                    "libvpx-vp9",
                    "-crf",
                    str(self.q),
                    "-b:v",
                    "0",
                ]
                + self.enc_args
                + [self.dst_pth]
            )
        return cmd

    def encode(self, every: int, threads: int, gpu_streams: int) -> DstVideo:
        """
        Run the encoder and return a DstVideo object.
        """
        cmd = self.set_enc_cmd()
        print(f"Encoding with {self.enc} (CRF {self.q})...")
        start_time = time.time()
        # SvtAv1EncApp uses a shell pipeline string; run via shell=True in that case.
        if self.enc == "svtav1":
            subprocess.run(cmd, check=True, capture_output=True, shell=True)
        else:
            subprocess.run(cmd, check=True, capture_output=True)
        self.time = time.time() - start_time
        return DstVideo(self.dst_pth, every, threads, gpu_streams)

    def remove_output(self) -> None:
        """
        Remove the output video file.
        """
        if os.path.exists(self.dst_pth):
            os.remove(self.dst_pth)


def psnr_to_mse(p: float, m: int) -> float:
    """
    Convert PSNR to MSE (Mean Squared Error). Used in weighted XPSNR calculation.
    """
    if p <= 0:
        return float(m**2)
    return (m**2) / (10 ** (p / 10))


def calc_some_scores(score_list: list[float]) -> tuple[float, float, float]:
    """
    Calculate the average, standard deviation, & 10th percentile of a list of scores.
    """
    if not score_list:
        return 0.0, 0.0, 0.0
    average: float = statistics.mean(score_list)
    std_dev: float = statistics.stdev(score_list) if len(score_list) > 1 else 0.0
    percentile_10th: float = statistics.quantiles(score_list, n=100)[10]
    return (average, std_dev, percentile_10th)
