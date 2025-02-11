#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13.1"
# dependencies = [
#     "argparse>=1.4.0",
#     "matplotlib>=3.10.0",
#     "numpy>=2.2.2",
#     "scipy>=1.15.1",
# ]
# ///

import argparse
import csv
import math
import os
from argparse import Namespace

import matplotlib.pyplot as plt
import numpy as np
from scipy.integrate import simpson
from scipy.interpolate import pchip_interpolate


def read_csv(filename):
    """
    Read CSV file and return data as dictionary of lists.
    Assumes CSV columns: 'q', 'output_filesize', 'ssimu2_hmean',
    'butter_distance', and 'wxpsnr'.
    """
    data = {
        "q": [],
        "output_filesize": [],
        "ssimu2_hmean": [],
        "butter_distance": [],
        "wxpsnr": [],
    }

    with open(filename, "r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            for key in data:
                data[key].append(float(row[key]))
    return data


def create_metric_plot(datasets, metric_name: str, fmt: str):
    """
    Create a plot for the specified metric for all given datasets.
    The datasets argument should be a list of tuples (label, data).
    Each dataset’s data is a dictionary (from read_csv), and label is the dataset identifier.
    """
    plt.figure(figsize=(10, 6))
    plt.style.use("dark_background")

    # For SSIMULACRA2, set background colors to black.
    if metric_name == "ssimu2_hmean":
        plt.gca().set_facecolor("black")
        plt.gcf().set_facecolor("black")

    # For each metric, define a colormap so that multiple CSV files
    # use different shades of the same base hue.
    colormaps = {
        "ssimu2_hmean": plt.cm.Blues,
        "butter_distance": plt.cm.YlOrBr,
        "wxpsnr": plt.cm.Reds,
    }
    cmap = colormaps.get(metric_name, plt.cm.viridis)

    n_datasets = len(datasets)
    # Iterate over datasets, computing a shade for each from the colormap.
    for idx, (label, df) in enumerate(datasets):
        # Normalize the index value for the colormap (between 0 and 1)
        color_value = (idx + 1) / (n_datasets + 1)
        line_color = cmap(color_value)
        filesize = df["output_filesize"]
        ydata = df[metric_name]
        plt.plot(
            filesize, ydata, marker="o", linestyle="-.", color=line_color, label=label
        )
        # Annotate each data point with its Q value. To avoid annotation overlap among datasets,
        # a small vertical offset is added depending on the dataset index.
        for i, (x, y) in enumerate(zip(filesize, ydata)):
            # Offset increases with dataset index
            offset = 10 + idx * 5
            plt.annotate(
                f"Q{df['q'][i]}",
                (x, y),
                textcoords="offset points",
                xytext=(0, offset),
                ha="center",
                color="white",
                fontsize=8,
            )

    # Set grid and axes formatting.
    plt.grid(True, color="grey", linestyle="--", linewidth=0.5, alpha=0.5)
    for spine in plt.gca().spines.values():
        spine.set_color("grey")

    # Set labels.
    plt.xlabel("Output Filesize (MB)", color="gainsboro", family="monospace")
    metric_labels = {
        "ssimu2_hmean": "SSIMULACRA2 Harmonic Mean",
        "butter_distance": "Butteraugli Distance",
        "wxpsnr": "W-XPSNR",
    }
    plt.ylabel(
        metric_labels.get(metric_name, metric_name),
        color="gainsboro",
        family="monospace",
    )

    # Set title.
    plt.title(
        f"Codec Comparison: {metric_labels.get(metric_name, metric_name)} vs Filesize",
        color="white",
        family="monospace",
        pad=12,
    )

    plt.tick_params(axis="both", colors="grey")
    plt.legend()
    plt.tight_layout()

    # Save the plot to file.
    output_filename = f"{metric_name}_plot.{fmt}"
    plt.savefig(output_filename, format=fmt)
    plt.close()


def bd_rate_simpson(metric_set1, metric_set2):
    """
    Calculate BD-rate (Bjontegaard Delta Rate) difference between two rate-distortion curves,
    using a Piecewise Cubic Hermite Interpolating Polynomial (PCHIP) and Simpson integration.

    Each metric_set is a list of tuples (bitrate, metric_value). The bitrate is first logged.
    The function computes the average percentage difference in bitrate over the overlapping interval
    of the metric curves.

    Returns BD-rate % as a float.
    """
    if not metric_set1 or not metric_set2:
        return 0.0
    try:
        # Sort each metric set by metric value.
        metric_set1.sort(key=lambda tup: tup[1])
        metric_set2.sort(key=lambda tup: tup[1])

        # For each set, take the logarithm of bitrate values and fix any infinite metric values.
        log_rate1 = [math.log(x[0]) for x in metric_set1]
        metric1 = [100.0 if x[1] == float("inf") else x[1] for x in metric_set1]
        log_rate2 = [math.log(x[0]) for x in metric_set2]
        metric2 = [100.0 if x[1] == float("inf") else x[1] for x in metric_set2]

        # Define the overlapping integration interval on the metric axis.
        min_int = max(min(metric1), min(metric2))
        max_int = min(max(metric1), max(metric2))
        if max_int <= min_int:
            return 0.0

        # Create 100 sample points between min_int and max_int.
        samples, interval = np.linspace(min_int, max_int, num=100, retstep=True)

        # Interpolate the log-rate values at the sample metric values.
        v1 = pchip_interpolate(metric1, log_rate1, samples)
        v2 = pchip_interpolate(metric2, log_rate2, samples)

        # Integrate the curves using Simpson's rule.
        int_v1 = simpson(v1, dx=interval)
        int_v2 = simpson(v2, dx=interval)

        # Compute the average difference in the log domain.
        avg_exp_diff = (int_v2 - int_v1) / (max_int - min_int)
    except (TypeError, ZeroDivisionError, ValueError):
        return 0.0

    # Convert the averaged log difference back to a percentage difference.
    bd_rate_percent = (math.exp(avg_exp_diff) - 1) * 100
    return bd_rate_percent


def main():
    parser = argparse.ArgumentParser(
        description="Plot codec metrics from one or more CSV files (one per codec) for side-by-side comparison."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        nargs="+",
        type=str,
        help="Path(s) to CSV file(s). Each CSV file should have the same columns.",
    )
    parser.add_argument(
        "-f",
        "--format",
        default="svg",
        type=str,
        help="Save the plot as 'svg', 'png', or 'webp'",
    )
    args: Namespace = parser.parse_args()
    csv_files = args.input
    fmt: str = args.format

    # Read all CSV files.
    datasets = []
    for filename in csv_files:
        data = read_csv(filename)
        label = os.path.basename(filename)
        datasets.append((label, data))

    # Create plots for each metric.
    metrics = ["ssimu2_hmean", "butter_distance", "wxpsnr"]
    for metric in metrics:
        create_metric_plot(datasets, metric, fmt)

    # If there are at least two datasets, compute and print the BD-rate for each metric.
    if len(datasets) >= 2:
        metric_labels = {
            "ssimu2_hmean": "\033[94mSSIMULACRA2\033[0m Harmonic Mean: ",
            "butter_distance": "\033[93mButteraugli\033[0m Distance:      ",
            "wxpsnr": "W-\033[91mXPSNR\033[0m:                   ",
        }

        # Compare the first CSV file with each of the other CSV files.
        for idx in range(1, len(datasets)):
            file1_label = datasets[0][0]
            filecmp_label = datasets[idx][0]
            print(
                "BD-rate values between '{}' & '{}'".format(file1_label, filecmp_label)
            )
            for metric in metrics:
                # Create lists of tuples (output_filesize, metric_value) for the two files.
                data1 = datasets[0][1]
                data2 = datasets[idx][1]
                metric_set1 = list(zip(data1["output_filesize"], data1[metric]))
                metric_set2 = list(zip(data2["output_filesize"], data2[metric]))

                bd_rate = bd_rate_simpson(metric_set1, metric_set2)
                # Decide which file is better based on the sign of the bd_rate value.
                if bd_rate < 0:
                    # Negative BD-rate indicates that the second file (the one it is compared with)
                    # is better (i.e., lower bitrate for the same quality).
                    winner_msg = f"{filecmp_label} is better"
                elif bd_rate > 0:
                    winner_msg = f"{file1_label} is better"
                else:
                    winner_msg = "No difference"

                print(
                    f"{metric_labels.get(metric, metric)}\033[1m{bd_rate:7.2f}%\033[0m -> {winner_msg}"
                )
            if idx < len(datasets) - 1:
                print()  # Empty line for readability
    else:
        print("Need at least two CSV files to compute BD-rate values.")


if __name__ == "__main__":
    main()
