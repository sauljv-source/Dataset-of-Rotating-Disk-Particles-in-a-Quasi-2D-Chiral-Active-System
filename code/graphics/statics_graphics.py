# Test static graphics
# Executed for each experiment, does not take long to run

import json
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.stats import gaussian_kde


def auto_find_csv():
    base = Path(__file__).resolve().parent.parent
    data_dir = base.parent / "processed_data" / "dataset"
    csv_files = sorted(data_dir.glob("**/*_trajectories.csv"))
    return csv_files[-1] if csv_files else None


def load_data(csv_path):
    if not csv_path.exists():
        print(f"Not found {csv_path}")
        exit(1)
    df = pd.read_csv(csv_path)
    print("Data loaded:", len(df), "rows,", df["particle"].nunique(), "particles")
    return df


def load_experiment_metadata(csv_path):
    meta_path = csv_path.with_name(csv_path.name.replace("_trajectories.csv", "_metadata.json"))
    if not meta_path.exists():
        print(f"Not found {meta_path}")
        exit(1)
    with open(meta_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    m = raw.get("metadata", raw)
    fps = m["recording"]["fps"]
    roi_radius = m["roi"]["radius_px"]
    part_diameter = m["particles"]["diameter_px"]
    part_radius = part_diameter // 2
    print(f"Metadata loaded: fps={fps}, roi_radius={roi_radius}, part_radius={part_radius}")
    return {"fps": fps, "roi_radius_px": roi_radius, "particle_diameter_px": part_diameter, "part_radius": part_radius}


# Trajectories plot
def plot_trajectories(df, output_dir, roi_radius, part_radius):
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    eff_radius = roi_radius - part_radius
    tracks = sorted(df["particle"].unique())
    cmap = plt.get_cmap("plasma", len(tracks))

    for i, track_id in enumerate(tracks):
        traj = df[df["particle"] == track_id]
        traj_sampled = traj.iloc[::10]
        ax.plot(traj_sampled["x"], traj_sampled["y"], "-", linewidth=0.3, alpha=0.6, color=cmap(i))

    wall = plt.Circle((0, 0), roi_radius, fill=False, edgecolor="crimson", linestyle="--", linewidth=2)
    ax.add_patch(wall)

    eff_wall = plt.Circle((0, 0), eff_radius, fill=False, edgecolor="orange", linestyle=":", linewidth=1.5, alpha=0.7)
    ax.add_patch(eff_wall)

    ax.scatter([0], [0], color="crimson", marker="x", s=120, linewidth=2)

    norm = plt.Normalize(vmin=0, vmax=max(1, len(tracks) - 1))
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="vertical", shrink=0.75, pad=0.02)
    cbar.set_label("Track ID", fontsize=11)

    ax.set_xlabel("x (px)")
    ax.set_ylabel("y (px)")
    ax.set_title("Particle trajectories (1:10 frames)", fontsize=14)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.15, linestyle=":")

    legend_elements = [
        Line2D([0], [0], color="crimson", linestyle="--", linewidth=2, label="Wall (%d px)" % roi_radius),
        Line2D([0], [0], color="orange", linestyle=":", linewidth=1.5, alpha=0.7, label="Center limit (%d px)" % eff_radius),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=9, framealpha=0.9)

    outpath = output_dir / "trajectories.png"
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


# Radial distribution plot
def plot_radial_distribution(df, output_dir, roi_radius, part_radius):
    eff_radius = roi_radius - part_radius
    df = df.copy()
    df["dist_center"] = np.sqrt(df["x"]**2 + df["y"]**2)
    dist = df["dist_center"].values
    N = len(dist)
    R = roi_radius

    fig, ax = plt.subplots(1, 1, figsize=(9, 5.5))

    counts, bin_edges = np.histogram(dist, bins=80, density=False)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    bin_widths = bin_edges[1:] - bin_edges[:-1]
    area_annulus = 2 * np.pi * bin_centers * bin_widths
    mean_density = N / (np.pi * R**2)
    g_r = counts / area_annulus / mean_density
    ax.bar(bin_centers, g_r, width=bin_widths, alpha=0.5, color="steelblue", edgecolor="white", linewidth=0.3, label="g(r)")

    x_grid = np.linspace(bin_centers[0], R * 1.05, 500)
    kde_func = gaussian_kde(dist)
    kde_vals = kde_func(x_grid)
    kde_g_r = kde_vals * R**2 / (2 * x_grid)
    ax.fill_between(x_grid, kde_g_r, alpha=0.25, color="steelblue")
    ax.plot(x_grid, kde_g_r, "-", color="steelblue", linewidth=2, label="g(r) KDE")

    mean_r = np.mean(dist)
    median_r = np.median(dist)
    ax.axvline(x=mean_r, color="navy", linestyle="--", linewidth=1.5, label="Mean = %.1f px" % mean_r, alpha=0.8)
    ax.axvline(x=median_r, color="royalblue", linestyle=":", linewidth=1.5, label="Median = %.1f px" % median_r, alpha=0.8)
    ax.axvline(x=roi_radius, color="crimson", linestyle="--", linewidth=2, label="Wall (%d px)" % roi_radius, alpha=0.8)
    ax.axvline(x=eff_radius, color="orange", linestyle=":", linewidth=1.5, label="Center limit (%d px)" % eff_radius, alpha=0.8)

    ax.set_xlabel("Distance to center (px)")
    ax.set_ylabel("g(r)")
    ax.set_title("Radial distribution function", fontsize=13)
    ax.legend(fontsize=8, framealpha=0.9, loc="upper right")
    ax.set_xlim(left=0)
    ax.grid(True, alpha=0.15, linestyle=":")

    fig.tight_layout()
    outpath = output_dir / "radial_distribution.png"
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


# Density map black
def plot_density_map(df, output_dir, roi_radius, part_radius):
    fig, ax = plt.subplots(1, 1, figsize=(10, 9))
    eff_radius = roi_radius - part_radius
    sampled = df.iloc[::5]

    fig.patch.set_facecolor("#0f0f0f")
    ax.set_facecolor("#110b1a")

    limit = roi_radius * 1.1
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    h = ax.hexbin(sampled["x"], sampled["y"], gridsize=80, cmap="inferno", linewidths=0.05, extent=[-limit, limit, -limit, limit], mincnt=0)
    cbar = fig.colorbar(h, ax=ax, shrink=0.8)
    cbar.set_label("N of visits (counts)", color="white")
    cbar.ax.tick_params(labelsize=9, colors="white")
    cbar.outline.set_edgecolor("white")
    cbar.outline.set_linewidth(0.5)

    wall = plt.Circle((0, 0), roi_radius, fill=False, color="cyan", linestyle="--", linewidth=2, alpha=0.8)
    ax.add_patch(wall)
    eff_wall = plt.Circle((0, 0), eff_radius, fill=False, color="lime", linestyle=":", linewidth=1.5, alpha=0.6)
    ax.add_patch(eff_wall)

    legend_elements = [
        Line2D([0], [0], color="cyan", linestyle="--", linewidth=2, label="Wall (%d px)" % roi_radius),
        Line2D([0], [0], color="lime", linestyle=":", linewidth=1.5, alpha=0.6, label="Center limit (%d px)" % eff_radius),
    ]
    legend = ax.legend(handles=legend_elements, loc="upper right", fontsize=9, framealpha=0.85)
    legend.get_frame().set_facecolor("#1a1a2e")
    legend.get_frame().set_edgecolor("white")
    for text in legend.get_texts():
        text.set_color("white")

    ax.set_xlabel("x (px)", color="white")
    ax.set_ylabel("y (px)", color="white")
    ax.tick_params(colors="white", labelsize=9)
    for spine in ax.spines.values():
        spine.set_color("white")
        spine.set_linewidth(0.5)
    ax.set_title("Occupancy map - most visited areas", fontsize=14, color="white")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.15, linestyle=":", color="white")

    outpath = output_dir / "density_map.png"
    fig.savefig(outpath, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


# Chirality metrics
def plot_chirality_metrics(w, df, output_dir, fps):
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.5))

    w_clean = w[~np.isnan(w)]
    w_mean = np.mean(w_clean)
    w_std = np.std(w_clean)

    x_grid = np.linspace(w_clean.min(), w_clean.max(), 500)
    kde_func = gaussian_kde(w_clean)
    kde_vals = kde_func(x_grid)

    axes[0].hist(w_clean, bins=100, density=True, alpha=0.45, color="darkviolet", edgecolor="white", linewidth=0.2, label="Histogram")
    axes[0].fill_between(x_grid, kde_vals, alpha=0.2, color="darkviolet")
    axes[0].plot(x_grid, kde_vals, "-", color="darkviolet", linewidth=2, label="KDE")
    axes[0].axvline(x=w_mean, color="black", linestyle="--", linewidth=1.5, label="Mean = %.1f rad/s" % w_mean, alpha=0.7)
    axes[0].axvline(x=0, color="gray", linestyle=":", linewidth=1, alpha=0.5)
    axes[0].annotate("$\\mu$ = %.1f\n$\\sigma$ = %.1f" % (w_mean, w_std), xy=(0.95, 0.95), xycoords="axes fraction", ha="right", va="top", fontsize=10, bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.8))

    axes[0].set_xlabel("Angular velocity $\\omega$ (rad/s)")
    axes[0].set_ylabel("Probability density")
    axes[0].set_title("Angular velocity distribution\n($\\omega>0$ = counter-clockwise, $\\omega<0$ = clockwise)", fontsize=12)
    axes[0].legend(fontsize=8, framealpha=0.9)
    axes[0].grid(True, alpha=0.15, linestyle=":")
    axes[0].set_xlim(w_mean - 5 * w_std, w_mean + 5 * w_std)
    mask_zoom = (x_grid >= w_mean - 5 * w_std) & (x_grid <= w_mean + 5 * w_std)
    ymax_zoom = np.max(kde_vals[mask_zoom]) * 1.3 if np.any(mask_zoom) else np.max(kde_vals) * 1.3
    axes[0].set_ylim(0, ymax_zoom)

    df_w = df.copy()
    df_w["w"] = w
    w_per_frame = df_w.groupby("frame")["w"].mean()
    time = w_per_frame.index / fps
    w_vals = w_per_frame.values

    window = 101
    if len(w_vals) > window:
        w_smooth = np.convolve(w_vals, np.ones(window)/window, mode="valid")
        w_std_smooth = np.convolve(
            np.abs(w_vals - np.convolve(w_vals, np.ones(window)/window, mode="same")),
            np.ones(window)/window, mode="valid"
        )
        t_smooth = np.convolve(time, np.ones(window)/window, mode="valid")
        axes[1].fill_between(t_smooth, w_smooth - w_std_smooth, w_smooth + w_std_smooth, alpha=0.15, color="teal")
        axes[1].plot(t_smooth, w_smooth, "-", color="teal", linewidth=1.5, label="Moving average (window=%d)" % window)
    else:
        axes[1].plot(time, w_vals, "-", color="teal", linewidth=0.6, alpha=0.7)

    axes[1].axhline(y=0, color="gray", linestyle=":", linewidth=1, alpha=0.5)
    if len(w_vals) > window:
        y_min = w_smooth.min() - 0.1 * abs(w_smooth.min())
        y_max = w_smooth.max() + 0.1 * abs(w_smooth.max())
        axes[1].set_ylim(y_min, y_max)
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("$\\langle \\omega \\rangle$ (rad/s)")
    axes[1].set_title("Mean angular velocity\n(average across all particles at each frame)", fontsize=12)
    axes[1].legend(fontsize=8, framealpha=0.9)
    axes[1].grid(True, alpha=0.15, linestyle=":")

    fig.tight_layout()
    outpath = output_dir / "chirality_metrics.png"
    fig.savefig(outpath, bbox_inches="tight")
    plt.close(fig)


def run(csv_path, output_dir=None):
    csv_path = Path(csv_path) if csv_path else auto_find_csv()
    if not csv_path:
        print("No --input provided nor CSV found in data")
        exit(1)

    if not output_dir:
        base_dir = Path(__file__).resolve().parent.parent
        exp_name = csv_path.stem.replace("_trajectories", "")
        output_dir = base_dir.parent / "processed_data" / "graphics" / exp_name
    else:
        output_dir = Path(output_dir)
        
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_data(csv_path)
    meta = load_experiment_metadata(csv_path)
    roi_radius = meta["roi_radius_px"]
    part_radius = meta["part_radius"]
    fps = meta["fps"]

    plot_trajectories(df, output_dir, roi_radius, part_radius)
    plot_radial_distribution(df, output_dir, roi_radius, part_radius)
    plot_density_map(df, output_dir, roi_radius, part_radius)

    csv_dir = csv_path.parent
    base = csv_path.parents[2]
    exp_name = csv_dir.name
    w_path = base / "metrics" / exp_name / f"{exp_name}_angular_velocity.npy"
    if w_path.exists():
        w = np.load(w_path)
        if len(w) != len(df):
            raise ValueError(f"Dimension error: len(w)={len(w)} does not match len(df)={len(df)}")
    else:
        raise FileNotFoundError(f"Filtered angular velocity file '{w_path}' does not exist.")
    plot_chirality_metrics(w, df, output_dir, fps)

    print(f"\nAll static plots generated in: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Input CSV file")
    parser.add_argument("--output-dir", help="Output directory for plots")
    args = parser.parse_args()
    run(args.input, args.output_dir)