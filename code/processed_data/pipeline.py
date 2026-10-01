'''
Takes raw .pkl data files, extracts relevant columns (frame, particle, x, y, theta).
Calculates angular velocity metrics, generates the clean CSV, metadata, and metrics.

The .pkl files always have the same 9 columns: frame, track, x, y, r, vx, vy, theta, w.

The output CSV has only 5: frame, particle, x, y, theta.

The angular velocity w is not included in the CSV (it is not a measured value, but calculated using a Savitzky–Golay smoothing filter).
We save it separately as a {experiment}_angular_velocity.npy file in the experiment's folder. We save it because we need it for the plots.
'''

import json
import argparse
import traceback
from pathlib import Path
import numpy as np
import pandas as pd

# Reading the .pkl file

def try_load_metadata(pkl_path):
    pkl_path = Path(pkl_path)
    base_name = pkl_path.name.replace("_w.pkl", "").replace(".pkl", "")
    base_path = pkl_path.parent / base_name
    for ext in [".json", ".txt"]:
        meta_path = base_path.with_suffix(ext)
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
    return None

# Converts them to integers

def _parse_roi_center(s):
    if pd.isna(s):
        return None
    try:
        return [int(x.strip()) for x in str(s).strip("[]").split(",")]
    except (ValueError, AttributeError):
        return None

# Reads tabla_experimentos.ods and returns a DataFrame

def load_experiments_table(ods_path):
    ods_path = Path(ods_path)
    if not ods_path.exists():
        return None
    try:
        df = pd.read_excel(ods_path, engine="odf")
        df["ID"] = df["ID"].astype(str).str.strip()
        return df
    except Exception as e:
        print(f"Could not read experiments table: {e}")
        return None

# Searches for the pkl hash in the experiments table

def lookup_experiment(pkl_path, table):
    stem = Path(pkl_path).stem
    for suffix in ["_w", "_raw", "_processed"]:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    matches = table[table["ID"] == stem]
    if matches.empty:
        return None
    if len(matches) == 1:
        return matches.iloc[0].to_dict()
    raise ValueError(f"Duplicate rows in the experiments table for ID: {stem}")


def discover_pkl_files(input_dir, pattern="*_w.pkl", max_files=None):
    input_path = Path(input_dir)
    if not input_path.is_dir():
        raise FileNotFoundError(f"Directory does not exist: {input_dir}")
    files = sorted(input_path.glob(pattern))
    if not files:
        files = sorted(input_path.glob("*.pkl"))
    if max_files and len(files) > max_files:
        files = files[:max_files]
    print(f"Found {len(files)} .pkl files in {input_dir}")
    return files

# {shape}_N{N}_P{P}_pf{phi}_fps{fps}_{id}_trajectories.csv (id are the first 8 characters of the hash)
# This is to ensure uniqueness for each experiment

def generate_fair_filename(exp_row, config):
    if exp_row is not None:
        shape = str(exp_row.get("particle_shape") or config.get("particle_shape") or "rotating_disk")
        N = int(exp_row["N"])
        P = exp_row["P"]
        phi = float(exp_row["phi"])
        fps = int(exp_row["fps"])
        exp_id = str(exp_row["ID"])[:8]
    else:
        shape = config.get("particle_shape") or "unknown"
        N = config.get("n_particles") or 0
        P = None
        phi = config.get("packing_fraction") or 0
        fps = 0
        exp_id = None

    shape_str = shape.replace(" ", "_")
    N_str = str(int(N))
    if P is not None:
        P_str = str(int(P)) if P == int(P) else f"{P:.1f}"
    else:
        P_str = ""
    pf_str = f"{float(phi):.2f}".replace(".", "")
    if pf_str.startswith("0") and len(pf_str) > 1:
        pf_str = pf_str[1:]
    fps_str = str(int(fps))

    parts = [shape_str, f"N{N_str}"]
    if P_str:
        parts.append(f"P{P_str}")
    parts.append(f"pf{pf_str}")
    parts.append(f"fps{fps_str}")
    if exp_id:
        parts.append(exp_id)
    parts.append("trajectories.csv")
    return "_".join(parts)

# Translation for metadata

def _illumination_label(raw):
    mapping = {
        "luzlejana": "far diffuse light",
        "luzcercana": "near diffuse light",
        "led": "LED",
        "laser": "laser",
    }
    return mapping.get(raw.lower().strip(), raw)

# Safe function (to avoid empty field errors)

def _safe(v, cast=None, default=None):
    if pd.isna(v) if hasattr(pd, 'isna') else (v is None):
        return default
    return cast(v) if cast else v

# Function to build metadata (merges .txt and .ods)

def build_experiment_metadata(
    pkl_meta,
    exp_row,
    fair_filename
):
    # Common data from any source
    def _from_either(key_txt, key_ods=None, cast_txt=None):
        val = None
        if pkl_meta is not None and key_txt in pkl_meta:
            val = pkl_meta[key_txt]
            if cast_txt:
                val = cast_txt(val)
        elif exp_row is not None:
            k = key_ods if key_ods else key_txt
            val = _safe(exp_row.get(k))
        return val

    N = _from_either("N", "N", int)
    P_val = _from_either("power", "P", float)
    phi = _from_either("packing_fraction", "phi", float)
    fps_val = _from_either("fps", "fps", int)
    if phi is not None:
        phi = round(phi, 6)

    fair_stem = Path(fair_filename).stem

    N_str = str(N) if N is not None else "?"
    phi_str = f"{phi:.2f}" if phi is not None else "?"
    shape_str = (pkl_meta or {}).get("particle_shape", "rotating disk")
    title = (
        f"Chiral active fluid of rotating disks: trajectory data of N={N_str} particles "
        f"in a circular confinement at packing fraction {phi_str}"
    )
    description = (
        f"Trajectory data from a chiral active fluid experiment with {shape_str} particles "
        f"driven by air flow. The dataset contains particle positions (x, y) and "
        f"orientation angle (theta) for N={N_str} particles "
        f"at packing fraction {phi_str}. "
    )
    if fps_val:
        description += f"Recordings were performed at {fps_val} fps using a high-speed camera. "
    description += (
        "The data is provided in CSV format with one file per experimental condition."
    )
    if pkl_meta and "system_diameter" in pkl_meta:
        description += f" The confinement is circular with a diameter of {pkl_meta['system_diameter']} m."

    meta = {
        "title": title,
        "description": description,
        "access_right": "open",
        "upload_type": "dataset",
        "license": "cc-by-4.0",
        "language": "eng",
        "keywords": [
            "active matter", "chiral active matter", "chiral fluids", "active chiral fluids",
            "active spinners", "chiral spinners", "rotating disks", "particle tracking",
            "packing fraction", "quasi-2D", "trajectory data", "macroscopic active matter", "soft matter",
        ],
        "creators": [
            {
                "name": "Jimenez Vela, Saul",
                "affiliation": "Universidad de Extremadura",
                "orcid": "0009-0002-2923-7047",
            },
        ],
        "contributors": [
            {
                "name": "Vega Reyes, Francisco",
                "affiliation": "Universidad de Extremadura",
                "type": "Supervisor",
                "orcid": "",
            },
        ],
        "references": [],
        "publication_date": "",
        "doi": "",
        "experiment_id": fair_stem,
        "date_recorded": "",
        "recording": {
            "original_filename": "",
            "frame_width_px": None,
            "frame_height_px": None,
            "fps": fps_val,
            "exposure": None,
            "exposure_units": "microseconds",
            "n_frames": None,
            "recording_time_s": None,
        },
        "camera": {
            "model": "",
            "distance_m": None,
            "pixel_ratio_px_per_m": None,
        },
        "optics": {
            "illumination_type": "",
            "illumination_power": None,
            "illumination_power_units": "watts",
        },
        "particles": {
            "N": N,
            "shape": "rotating disk",
            "material": "",
            "diameter_px": None,
            "diameter_m": None,
        },
        "system": {
            "confinement_shape": "circle",
            "system_diameter_m": None,
            "packing_fraction": phi,
            "boundary_conditions": "solid wall (no-slip)",
        },
        "medium": {
            "viscosity_pas": None,
            "temperature_k": None,
            "confinement_height_m": None,
        },
        "air_flow": {
            "description": "air flow from below to fluidize particles",
            "pressure": "",
            "flow_rate": "",
            "flow_rate_units": "",
        },
        "roi": {
            "center_x_px": None,
            "center_y_px": None,
            "radius_px": None,
            "origin": "top-left corner of frame",
        },
        "tracking": {
            "method": "centroid-based tracking",
            "spatial_resolution_m_per_px": None,
            "temporal_resolution_fps": fps_val,
            "total_observation_time_s": None,
            "n_trajectories": N,
            "localization_error_px": "",
            "trajectory_completeness_pct": "",
        },
        "units": {
            "position": "pixels (relative to ROI center)",
            "theta": "radians [0, 2pi)",
            "time": "seconds (frame / fps)",
        },
        "quality_indicators": {
            "mean_trajectory_length_frames": None,
            "signal_to_noise_ratio": "",
            "boundary_artifact_zones": "",
        },
        "associated_files": {
            "trajectory_file": fair_filename,
            "code_repository": "",
        },
    }

    # Populate from pkl_meta (.txt)
    
    if pkl_meta is not None:
        meta["date_recorded"] = str(pkl_meta.get("date", ""))

        rec = meta["recording"]
        if "original_file" in pkl_meta:
            rec["original_filename"] = Path(pkl_meta["original_file"]).name
        shape_ = pkl_meta.get("shape")
        if isinstance(shape_, (list, tuple)) and len(shape_) >= 2:
            rec["frame_width_px"] = int(shape_[0])
            rec["frame_height_px"] = int(shape_[1])
        if "fps" in pkl_meta:
            rec["fps"] = int(pkl_meta["fps"])
        if "exposure" in pkl_meta:
            rec["exposure"] = int(pkl_meta["exposure"])
        if "n_frames" in pkl_meta:
            rec["n_frames"] = int(pkl_meta["n_frames"])
        if "recording_time" in pkl_meta:
            rec["recording_time_s"] = round(float(pkl_meta["recording_time"]), 2)

        cam = meta["camera"]
        if "camera_distance" in pkl_meta:
            cam["distance_m"] = float(pkl_meta["camera_distance"])
        if "pixel_ratio" in pkl_meta:
            cam["pixel_ratio_px_per_m"] = round(float(pkl_meta["pixel_ratio"]), 2)

        opt = meta["optics"]
        if "lights" in pkl_meta:
            opt["illumination_type"] = _illumination_label(str(pkl_meta["lights"]))
        if "power" in pkl_meta:
            opt["illumination_power"] = int(pkl_meta["power"])

        par = meta["particles"]
        if "particle_shape" in pkl_meta:
            par["shape"] = str(pkl_meta["particle_shape"])
        if "particle_diameter_px" in pkl_meta:
            par["diameter_px"] = int(pkl_meta["particle_diameter_px"])
        if "particle_diameter_m" in pkl_meta:
            par["diameter_m"] = float(pkl_meta["particle_diameter_m"])

        sys_cfg = meta["system"]
        if "system_diameter" in pkl_meta:
            sys_cfg["system_diameter_m"] = float(pkl_meta["system_diameter"])

        roi = meta["roi"]
        roi_center = pkl_meta.get("ROI_center")
        if isinstance(roi_center, (list, tuple)) and len(roi_center) >= 2:
            roi["center_x_px"] = int(roi_center[0])
            roi["center_y_px"] = int(roi_center[1])
        if "ROI_radius" in pkl_meta:
            roi["radius_px"] = int(pkl_meta["ROI_radius"])

        trk = meta["tracking"]
        if "particle_diameter_px" in pkl_meta and "camera_distance" in pkl_meta:
            trk["spatial_resolution_m_per_px"] = round(
                float(pkl_meta.get("particle_diameter_m", 0))
                / float(pkl_meta["particle_diameter_px"]),
                6,
            ) if pkl_meta.get("particle_diameter_px", 0) else None
        if "recording_time" in pkl_meta:
            trk["total_observation_time_s"] = round(float(pkl_meta["recording_time"]), 2)
        if "n_frames" in pkl_meta:
            meta["quality_indicators"]["mean_trajectory_length_frames"] = int(pkl_meta["n_frames"])

    # Populate from (.ods) for fields that (.txt) does not cover
    
    if exp_row is not None:
        air = meta["air_flow"]
        u_air = _safe(exp_row.get("u_air"), float)
        if u_air is not None:
            air["description"] = f"air flow from below to fluidize particles ({u_air} m/s)"

        if meta["recording"]["recording_time_s"] is None:
            Tt = _safe(exp_row.get("Tt"), float)
            if Tt is not None:
                meta["recording"]["recording_time_s"] = round(Tt, 2)

        if meta["roi"]["center_x_px"] is None:
            roi_c = _parse_roi_center(exp_row.get("ROI_center"))
            if roi_c is not None and len(roi_c) >= 2:
                meta["roi"]["center_x_px"] = roi_c[0]
                meta["roi"]["center_y_px"] = roi_c[1]
        if meta["roi"]["radius_px"] is None:
            rr = _safe(exp_row.get("ROI_radius"), int)
            if rr is not None:
                meta["roi"]["radius_px"] = rr

    if meta["particles"]["N"] is not None:
        meta["tracking"]["n_trajectories"] = meta["particles"]["N"]

    # Wrap in "metadata" for Zenodo API compatibility
    
    meta = {"metadata": meta}
    return meta

def process_single_pkl(pkl_path, config):
    pkl_path = Path(pkl_path)
    result = {
        "pkl": str(pkl_path),
        "success": False,
        "error": None,
        "csv": None,
    }

    # Clean up the experiment from previous iterations
    config["_exp_row"] = None

    try:
        # Search for the experiment in the .ods table
        if config.get("_exp_table") is None:
            raise RuntimeError("Experiments table (.ods) not loaded; cannot process experiment")
        exp_row = lookup_experiment(pkl_path, config["_exp_table"])
        config["_exp_row"] = exp_row
        if exp_row is None:
            raise RuntimeError(f"Experiment {pkl_path.name} not found in the .ods table")
        # Load metadata from the attached .txt file
        pkl_meta = try_load_metadata(pkl_path)
        config["_pkl_meta"] = pkl_meta

        # Load the pickle
        df = pd.read_pickle(pkl_path)

        # Select the columns of interest
        # The .pkl always has: frame, track, x, y, r, vx, vy, theta, w; we keep: frame, track, x, y, theta
        selected_cols = ["frame", "track", "x", "y", "theta", "w", "vx", "vy"]
        df = df[selected_cols].copy()

        # Convert theta from blades to radians, w from blades/frame to rad/s.
        # fps always comes from the actual experiment row in the .ods table.
        fps = int(exp_row["fps"])
        BLADES_PER_REVOLUTION = 14
        factor = 2 * np.pi / BLADES_PER_REVOLUTION
        df["theta"] = df["theta"] * factor
        df["w"] = df["w"] * factor * fps

        # Rename: track -> particle (as requested in Appendix I)
        df.rename(columns={"track": "particle"}, inplace=True)

        # Generate FAIR CSV name
        csv_name = generate_fair_filename(exp_row, config)
        csv_stem_name = Path(csv_name).stem
        exp_stem = csv_stem_name.replace("_trajectories", "")
        exp_dir_path = Path(config["output_resultados"]) / exp_stem
        exp_dir_path.mkdir(parents=True, exist_ok=True)
        csv_path = exp_dir_path / csv_name

        # Save w separately and then the CSV
        metrics_dir_path = Path(config["output_metrics"]) / exp_stem
        metrics_dir_path.mkdir(parents=True, exist_ok=True)
        w_path = metrics_dir_path / f"{exp_stem}_angular_velocity.npy"
        np.save(w_path, df["w"].values)
        df[["frame", "particle", "x", "y", "theta"]].to_csv(csv_path, index=False, float_format="%.15g")

        # Calculate metrics
        metrics = {}

        w_values = []
        dr_values = []
        v_values = []
        for particle_id in df["particle"].unique():
            mask = df["particle"] == particle_id
            data = df.loc[mask]
            theta = data["theta"].values
            w = data["w"].values
            x = data["x"].values
            y = data["y"].values
            vx = data["vx"].values
            vy = data["vy"].values

            w_values.extend(w)

            v = np.sqrt(vx**2 + vy**2)
            v_values.extend(v)

            # Dr: subtract mean rotation before MSAD
            unwrapped_theta = np.unwrap(theta, period=2 * np.pi)

            n = len(unwrapped_theta)
            if n > 100:
                t_vals = np.arange(n, dtype=float) / fps
                # Fit a line to theta(t) to get mean_omega
                theta_slope = np.polyfit(t_vals, unwrapped_theta, 1)[0]
                # Residuals: fluctuations around mean rotation
                theta_residual = unwrapped_theta - theta_slope * t_vals
                max_tau = min(n // 4, 500)
                if max_tau > 5:
                    taus = np.arange(1, max_tau + 1, dtype=float) / fps
                    msad = np.array([
                        np.mean((theta_residual[i:] - theta_residual[:-i])**2)
                        for i in range(1, max_tau + 1)
                    ])
                    slope = np.polyfit(taus, msad, 1)[0]
                    dr = slope / 2.0
                    if dr > 0:
                        dr_values.append(dr)

        w_values = np.array(w_values)
        v_values = np.array(v_values)
        metrics["mean_angular_velocity"] = float(np.mean(w_values))
        metrics["std_angular_velocity"] = float(np.std(w_values))
        metrics["net_chirality"] = float(np.mean(np.sign(w_values)))
        metrics["abs_mean_w"] = float(np.mean(np.abs(w_values)))
        metrics["mean_speed_px_per_s"] = float(np.mean(v_values))
        metrics["n_particles"] = int(df["particle"].nunique())
        metrics["n_frames"] = int(df["frame"].nunique())
        metrics["fps"] = fps

        # Curvature radius: <|v|> / <|w|>
        mean_v = float(np.mean(v_values))
        mean_abs_w = float(np.mean(np.abs(w_values)))
        curvature_radius = mean_v / mean_abs_w if mean_abs_w > 0 else None
        if curvature_radius is not None:
            metrics["curvature_radius_px"] = curvature_radius

        # Rotational diffusion coefficient
        mean_dr = float(np.mean(dr_values)) if dr_values else None
        if mean_dr is not None:
            metrics["rotational_diffusion_coefficient"] = mean_dr

        # Save metrics
        metrics_path = metrics_dir_path / f"{exp_stem}_metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

        # Generate and save metadata
        meta = build_experiment_metadata(
            pkl_meta=pkl_meta,
            exp_row=config.get("_exp_row"),
            fair_filename=csv_name,
        )
        meta_path = exp_dir_path / f"{exp_stem}_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        result["csv"] = str(csv_path)
        result["success"] = True

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        print(f"[{pkl_path.name}] error: {e}")
        print(traceback.format_exc())

    return result


def run(input_dir, output_dir=None, force=False, max_files=None):
    input_dir = Path(input_dir).resolve()
    if output_dir:
        output_base = Path(output_dir).resolve()
    else:
        processed_data_dir = input_dir.parent / "processed_data"
        output_base = processed_data_dir / "dataset"

    output_metrics = input_dir.parent / "processed_data" / "metrics"
    output_resultados = output_base

    for d in [output_metrics, output_resultados]:
        Path(d).mkdir(parents=True, exist_ok=True)

    config = {
        "skip_existing_csv": not force,
        "output_resultados": str(output_resultados),
        "output_metrics": str(output_metrics),
    }

    ods_path = input_dir / "tabla_experimentos.ods"
    if ods_path.exists():
        config["_exp_table"] = load_experiments_table(ods_path)
        if config["_exp_table"] is not None:
            print(f"Experiments table loaded: {ods_path} ({len(config['_exp_table'])} rows)")
    else:
        print(f"Experiments table not found in {ods_path}")

    try:
        pkls = discover_pkl_files(input_dir, "*_w.pkl", max_files)
    except FileNotFoundError as e:
        print(str(e))
        exit(1)

    if not pkls:
        print("No .pkl files found. Exiting.")
        exit(0)

    results = []
    for pkl in pkls:
        res = process_single_pkl(pkl, config)
        results.append(res)

    n_ok = sum(1 for r in results if r["success"])
    n_fail = len(results) - n_ok

    print(f"\nProcessing completed: {n_fail} failures")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TFG Data Processing Pipeline")
    parser.add_argument("--input_dir", type=str, required=True, help="Directory where .pkl files are located")
    parser.add_argument("--output_dir", type=str, default=None, help="Root output directory (default: next to input_dir)")
    parser.add_argument("--force", action="store_true", default=False, help="Force reprocessing even if CSV already exists")
    parser.add_argument("--max_files", type=int, default=None, help="Process only N files (for testing)")
    args = parser.parse_args()
    run(args.input_dir, args.output_dir, args.force, args.max_files)