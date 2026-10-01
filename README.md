TFG project: tracking data from rotating disk particles in a quasi-2D chiral active fluid. Particles are fluidized with air flow and recorded with a high-speed camera.

Each experiment gives you a csv (frame, particle, x, y, theta) and a json with metadata.

Csv and json file names include the experiment parameters:

rotating_disk_N{number}_P{power}_pf{packing}_fps{fps}_{hash}_trajectories.csv
rotating_disk_N{number}_P{power}_pf{packing}_fps{fps}_{hash}_metadata.json

N = particle count, P = power, pf = packing fraction x100 (pf25 = 0.25), fps = frames per second, hash = first 8 chars of the experiment md5.

115 experiments total.

-------------------------------------------------------------------------------

Open a terminal in TFG/code/. Install dependencies with pip install -r requirements.txt (you might want a virtual env first).

To run everything:
  python run_all.py --input_dir "..\raw_data" --skip-zenodo

One step at a time:
  python processed_data/pipeline.py --input_dir "..\raw_data"   (generates csv, metadata and metrics for each experiment)
  python graphics/statics_graphics.py                           (generates png plots: trajectories, radial distribution, density map, chirality)
  python graphics/animate_graphic.py                            (generates mp4 video of particles moving over time)
  python zenodo/post_zenodo.py                                  (uploads csvs and metadata to Zenodo Sandbox)

raw_data has the .pkl files.
processed_data has the csvs, plots and metrics.

Flags for run_all.py: --force reprocesses even if csv exists, --max_files N limits how many .pkl files to process, --skip-zenodo skips upload.