# Animated graphic test
# Executed for each experiment, takes a bit to complete (833 frames, about 30 seconds)

import matplotlib
matplotlib.use('Agg')
import json
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle
import imageio


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


def _build_plot_setup(df, roi_radius, part_radius):
    # Returns roi_radius, part_radius, eff_radius, tracks, n_tracks, cmap
    eff_radius = roi_radius - part_radius
    tracks = sorted(df["particle"].unique())
    n_tracks = len(tracks)
    cmap = plt.get_cmap("plasma", max(1, n_tracks))
    return roi_radius, part_radius, eff_radius, tracks, n_tracks, cmap


def _build_trails(df, all_frames, tracks, trail_length):
    # Builds trails and curr_positions for a list of frames
    sampled = df[df["frame"].isin(all_frames)]
    frame_groups = {f: g for f, g in sampled.groupby("frame")}
    n_frames = len(all_frames)

    trails = {t: [[] for _ in range(n_frames)] for t in tracks}
    current_trail = {t: [] for t in tracks}
    curr_positions = [{} for _ in range(n_frames)]

    for fi, frame in enumerate(all_frames):
        if frame in frame_groups:
            fg = frame_groups[frame]
            for _, row in fg.iterrows():
                t = int(row["particle"])
                x, y = row["x"], row["y"]
                curr_positions[fi][t] = (x, y)
                current_trail[t].append((x, y))
                if len(current_trail[t]) > trail_length:
                    current_trail[t].pop(0)

        for t in tracks:
            if t not in curr_positions[fi]:
                current_trail[t] = []

        for t in tracks:
            trails[t][fi] = list(current_trail[t])

    return trails, curr_positions, frame_groups, n_frames


def make_animation_bodies_tracked(df, output_dir, filename="animation_bodies_tracked.mp4", step=30, trail_length=50, fps_input=900, fps_output=30, max_frames=None, roi_radius=408, part_radius=39):
    roi_radius, part_radius, eff_radius, tracks, n_tracks, cmap = _build_plot_setup(df, roi_radius, part_radius)

    all_frames = np.arange(df["frame"].min(), df["frame"].max() + 1, step)
    if max_frames and len(all_frames) > max_frames:
        all_frames = all_frames[:max_frames]

    trails, curr_positions, _, n_frames = _build_trails(df, all_frames, tracks, trail_length)

    fig, ax = plt.subplots(figsize=(10, 10))

    wall = plt.Circle((0, 0), roi_radius, fill=False, edgecolor="crimson", linestyle="--", linewidth=2)
    ax.add_patch(wall)
    eff_wall = plt.Circle((0, 0), eff_radius, fill=False, edgecolor="orange", linestyle=":", linewidth=1.5, alpha=0.5)
    ax.add_patch(eff_wall)
    ax.scatter([0], [0], color="crimson", marker="x", s=100, linewidth=2)

    lim = roi_radius * 1.08
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.set_xlabel("x (px)")
    ax.set_ylabel("y (px)")
    ax.set_title("Particle trajectories over time (with bodies)", fontsize=14)
    ax.grid(True, alpha=0.1, linestyle=":")

    legend_elements = [
        Line2D([0], [0], color="crimson", linestyle="--", linewidth=2, label="Wall (%d px)" % roi_radius),
        Line2D([0], [0], color="orange", linestyle=":", linewidth=1.5, alpha=0.5, label="Center limit (%d px)" % eff_radius),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=9, framealpha=0.9)

    lines = {}
    for i, t in enumerate(tracks):
        l, = ax.plot([], [], "-", color=cmap(i), linewidth=0.5, alpha=0.6)
        lines[t] = l

    particle_circles = []
    for i, t in enumerate(tracks):
        c = Circle((0, 0), part_radius, facecolor=cmap(i), edgecolor="none", alpha=0.85, zorder=4)
        ax.add_patch(c)
        particle_circles.append(c)

    particle_labels = []
    for i, t in enumerate(tracks):
        lbl = ax.text(0, 0, str(t), fontsize=8, fontweight="bold", color="white", ha="center", va="center", bbox=dict(boxstyle="round,pad=0.1", facecolor=cmap(i), edgecolor="none", alpha=0.85), zorder=6, visible=False)
        particle_labels.append(lbl)

    time_text = ax.text(0.02, 0.95, "", transform=ax.transAxes, fontsize=14, bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.85))

    outpath = output_dir / filename
    writer = imageio.get_writer(outpath, fps=fps_output, codec="libx264", quality=8, pixelformat="yuv420p")

    fig.tight_layout()

    for fi in range(n_frames):
        for t in tracks:
            pts = np.array(trails[t][fi])
            if len(pts) > 0:
                lines[t].set_data(pts[:, 0], pts[:, 1])
            else:
                lines[t].set_data([], [])

        data = curr_positions[fi]
        for i, t in enumerate(tracks):
            if t in data:
                particle_circles[i].set_center(data[t])
                particle_circles[i].set_visible(True)
            else:
                particle_circles[i].set_center((0, 0))
                particle_circles[i].set_visible(False)

        for i, t in enumerate(tracks):
            if t in data:
                particle_labels[i].set_position(data[t])
                particle_labels[i].set_visible(True)
            else:
                particle_labels[i].set_visible(False)

        tiempo = all_frames[fi] / fps_input
        time_text.set_text("t = %.1f s" % tiempo)

        fig.canvas.draw()
        image = np.asarray(fig.canvas.buffer_rgba())[:, :, :3]
        writer.append_data(image)

    writer.close()
    plt.close(fig)

def run(csv_path, output_dir=None, step=30, trail_length=50, fps_output=30, max_frames=None):
    csv_path = Path(csv_path) if csv_path else auto_find_csv()
    if not csv_path or not csv_path.exists():
        print("Error, no --input provided nor CSV found in data folder")
        exit(1)

    if not output_dir:
        exp_name = csv_path.stem.replace("_trajectories", "")
        output_dir = csv_path.parent.parent / "graphics" / exp_name
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_data(csv_path)
    meta = load_experiment_metadata(csv_path)
    roi_radius = meta["roi_radius_px"]
    part_radius = meta["part_radius"]
    fps = meta["fps"]

    make_animation_bodies_tracked(df, output_dir, filename="animation_bodies_tracked.mp4", step=step, trail_length=trail_length, fps_input=fps, fps_output=fps_output, max_frames=max_frames, roi_radius=roi_radius, part_radius=part_radius)

    print(f"\nAll videos generated in: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="Input CSV file")
    parser.add_argument("--output-dir", help="Output directory for videos")
    args = parser.parse_args()
    run(args.input, args.output_dir)