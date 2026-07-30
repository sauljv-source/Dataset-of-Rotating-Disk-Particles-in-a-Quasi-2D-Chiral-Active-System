# Complete block to run all .py files at once in order and prevent any missing file errors

import os
import glob
import argparse


def main():
    parser = argparse.ArgumentParser(description="Run complete pipeline")
    parser.add_argument("--input_dir", type=str, required=True, help="Directory containing the .pkl files")
    parser.add_argument("--output_dir", type=str, default=None, help="Root output directory")
    parser.add_argument("--force", action="store_true", default=False, help="Force reprocessing even if the CSV already exists")
    parser.add_argument("--max_files", type=int, default=None, help="Process only N files (for testing)")
    parser.add_argument("--skip-zenodo", action="store_true", default=False, help="Skip upload to Zenodo")
    args = parser.parse_args()

    from processed_data.pipeline import run as pipeline_run
    from graphics.statics_graphics import run as static_plots_run
    from graphics.animate_graphic import run as video_run
    from zenodo.post_zenodo import run as zenodo_run

    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir) if args.output_dir else None

    # Pipeline
    print("\nStep 1: Processing pipeline\n")
    try:
        pipeline_run(input_dir, output_dir, force=args.force, max_files=args.max_files)
    except Exception as e:
        print(f"Unexpected error: {e}")
        exit(1)

    # Results directory
    if output_dir:
        results_dir = output_dir
    else:
        results_dir = os.path.join(os.path.dirname(input_dir), "processed_data", "dataset")

    if not os.path.isdir(results_dir):
        print(f"Error, directory not found: {results_dir}")
        exit(1)

    exp_dirs = sorted(glob.glob(os.path.join(results_dir, "*")))
    exp_dirs = [d for d in exp_dirs if os.path.isdir(d)]
    if not exp_dirs:
        print(f"Error, no experiments found in: {results_dir}")
        exit(1)

    n_fail = 0
    for exp_dir in exp_dirs:
        exp_name = os.path.basename(exp_dir)
        graphics_dir = os.path.join(exp_dir, "graphics")
        os.makedirs(graphics_dir, exist_ok=True)

        csv_path = os.path.join(exp_dir, exp_name + "_trajectories.csv")
        if not os.path.exists(csv_path):
            print(f"\nWarning, file not found: {csv_path}")
            n_fail += 1
            continue

        # Final plots
        print("\nStep 2: Plots\n")
        try:
            static_plots_run(csv_path, output_dir=graphics_dir)
        except Exception as e:
            print(f"Error in static plots for {exp_name} : {e}")
            n_fail += 1
            continue

        # Test animation
        print("\nStep 3: Video\n")
        try:
            video_run(csv_path, output_dir=graphics_dir)
        except Exception as e:
            print(f"Error in videos for {exp_name} : {e}")
            n_fail += 1
            continue

    # Zenodo upload
    print("\nStep 4: Upload to Zenodo Sandbox\n")
    if not args.skip_zenodo:
        try:
            zenodo_run()
        except Exception as e:
            print(f"Error, upload to Zenodo failed: {e}")
            exit(1)
        print("Upload to Zenodo completed.")
    else:
        print("Upload to Zenodo skipped by --skip-zenodo")

    print(f"\nProcess finished: failures = {n_fail}")
    print(f"Experiments saved to: {results_dir}\n")

if __name__ == "__main__":
    main()