# Automatic script to build one ZIP with the .csv and .json of each experiment and upload it to Zenodo Sandbox

import requests
import os
import json
import zipfile
from dotenv import load_dotenv
from pathlib import Path


URL = "https://sandbox.zenodo.org/api/deposit/depositions"
ZIP_NAME = "rotating_disk_dataset.zip"


def run():
    load_dotenv()
    TOKEN = os.getenv("Token_Zenodo_Sandbox")
    if not TOKEN:
        print("The environment variable 'TOKEN' is not configured.")
        exit(1)

    json_headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json'
    }

    file_headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/octet-stream'
    }

    global_metadata_file = Path(__file__).parent.parent.parent / "global_metadata.json"
    dataset_dir = Path(__file__).parent.parent.parent / "processed_data" / "dataset"
    if not global_metadata_file.exists():
        print(f"Global metadata file not found: {global_metadata_file}")
        exit(1)

    with open(global_metadata_file, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    if not dataset_dir.is_dir():
        print(f"Directory not found: {dataset_dir}")
        exit(1)

    exp_folders = sorted([
        p for p in dataset_dir.iterdir()
        if p.is_dir() and list(p.glob("*_trajectories.csv"))
    ])

    if not exp_folders:
        print(f"No experiments found (subfolders with *_trajectories.csv) in: {dataset_dir}")
        exit(1)

    print(f"Experiments found: {len(exp_folders)}")

    zip_path = dataset_dir.parent / ZIP_NAME
    n_fail = 0
    n_files = 0

    print(f"\nBuilding ZIP: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in exp_folders:
            csv_files = sorted(folder.glob("*_trajectories.csv"))
            meta_files = sorted(folder.glob("*_metadata.json"))

            if not meta_files:
                print(f"No metadata found in {folder.name}.")
                n_fail += 1

            for file_path in csv_files + meta_files:
                zf.write(file_path, arcname=f"{folder.name}/{file_path.name}")
                n_files += 1

    print(f"ZIP built: {zip_path} ({zip_path.stat().st_size / 1048576:.1f} MB, {n_files} files)")

    r = requests.post(URL, json={}, headers=json_headers)
    print(f"\nServer status code: {r.status_code}")
    if r.status_code == 201:
        print("Resource in Zenodo Sandbox successfully generated.")
        data = r.json()
        data_id = data['id']
        data_url = data['links']['bucket']
        print(f"Deposit created successfully. ID: {data_id}")
    else:
        print(f"The server rejected the request: {r.text}")
        print(f"\nUpload finished: {n_files} files in 1 ZIP, {n_fail + 1} failures")
        exit(1)

    with open(zip_path, "rb") as fp:
        r_file = requests.put(f"{data_url}/{ZIP_NAME}", data=fp, headers=file_headers)

    if r_file.status_code not in (200, 201):
        print(f"Error uploading ZIP {ZIP_NAME}: {r_file.text}")
        print(f"\nUpload finished: {n_files} files in 1 ZIP, {n_fail + 1} failures")
        exit(1)

    r_metadata = requests.put(f"{URL}/{data_id}", headers=json_headers, json=metadata)
    if r_metadata.status_code == 200:
        print("Global metadata saved successfully.")
    else:
        print(f"Error updating global metadata: {r_metadata.text}")
        n_fail += 1

    if n_fail:
        print(f"\nUpload finished: {n_files} files in 1 ZIP, {n_fail} failures")
        exit(1)

    r_publication = requests.post(f"{URL}/{data_id}/actions/publish", headers=json_headers)
    if r_publication.status_code == 202:
        print("\nDeposit officially published on Zenodo Sandbox.")
        print(f"Web link: {r_publication.json().get('links', {}).get('html', 'Not available')}")
        print(f"\nUpload finished: {n_files} files in 1 ZIP, no failures")
    else:
        print(f"Error publishing: {r_publication.text}")
        print(f"\nUpload finished: {n_files} files in 1 ZIP, 1 failure")
        exit(1)


if __name__ == "__main__":
    run()
