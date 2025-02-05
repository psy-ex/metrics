#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13.1"
# dependencies = [
#     "argparse>=1.4.0",
#     "matplotlib>=3.10.0",
# ]
# ///

import argparse
import csv
import os
from argparse import Namespace

import matplotlib.pyplot as plt


def read_csv(filename):
    """
    Read CSV file and return data as dictionary of lists.
    Assumes CSV columns: 'q', 'output_filesize', 'ssimu2_hmean',
    'butter_distance', and 'wxpsnr'.
    """
    data = {
        'q': [],
        'output_filesize': [],
        'ssimu2_hmean': [],
        'butter_distance': [],
        'wxpsnr': []
    }

    with open(filename, 'r') as csvfile:
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
    if metric_name == 'ssimu2_hmean':
        plt.gca().set_facecolor("black")
        plt.gcf().set_facecolor("black")

    # For each metric, define a colormap so that multiple CSV files
    # use different shades of the same base hue.
    colormaps = {
        'ssimu2_hmean': plt.cm.Blues,
        'butter_distance': plt.cm.YlOrBr,
        'wxpsnr': plt.cm.Reds,
    }
    cmap = colormaps.get(metric_name, plt.cm.viridis)

    n_datasets = len(datasets)
    # Iterate over datasets, computing a shade for each from the colormap.
    for idx, (label, df) in enumerate(datasets):
        # Normalize the index value for the colormap (between 0 and 1)
        color_value = (idx + 1) / (n_datasets + 1)
        line_color = cmap(color_value)
        filesize = df['output_filesize']
        ydata = df[metric_name]
        plt.plot(filesize, ydata, marker="o", linestyle="-.", color=line_color, label=label)
        # Annotate each data point with its Q value. To avoid annotation overlap among datasets,
        # a small vertical offset is added depending on the dataset index.
        for i, (x, y) in enumerate(zip(filesize, ydata)):
            # Offset increases with dataset index
            offset = 10 + idx * 5
            plt.annotate(
                f'{label}:Q{df["q"][i]}',
                (x, y),
                textcoords="offset points",
                xytext=(0, offset),
                ha="center",
                color="white",
                fontsize=8
            )

    # Set grid and axes formatting.
    plt.grid(True, color="grey", linestyle="--", linewidth=0.5, alpha=0.5)
    for spine in plt.gca().spines.values():
        spine.set_color("grey")

    # Set labels.
    plt.xlabel("Output Filesize (KB)", color="gainsboro", family="monospace")
    metric_labels = {
        'ssimu2_hmean': 'SSIMULACRA2 Harmonic Mean',
        'butter_distance': 'Butteraugli Distance',
        'wxpsnr': 'W-XPSNR'
    }
    plt.ylabel(metric_labels.get(metric_name, metric_name), color="gainsboro", family="monospace")

    # Set title.
    plt.title(
        f"Codec Comparison: {metric_labels.get(metric_name, metric_name)} vs Filesize",
        color="white",
        family="monospace",
        pad=12
    )

    plt.tick_params(axis="both", colors="grey")
    plt.legend()
    plt.tight_layout()

    # Save the plot to file.
    output_filename = f'{metric_name}_plot.{fmt}'
    plt.savefig(output_filename, format=fmt)
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Plot codec metrics from one or more CSV files (one per codec) for side-by-side comparison."
    )
    parser.add_argument(
        "-i", "--input", required=True, nargs="+", type=str,
        help="Path(s) to CSV file(s). Each CSV file should have the same columns."
    )
    parser.add_argument(
        "-f",
        "--format",
        required=False,
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
    metrics = ['ssimu2_hmean', 'butter_distance', 'wxpsnr']
    for metric in metrics:
        create_metric_plot(datasets, metric, fmt)


if __name__ == "__main__":
    main()
