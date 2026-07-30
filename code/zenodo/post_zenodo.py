# Automatic script to upload global JSON as metadata and .csv + .json for each experiment as downloadable files
# Zip?

import requests
import os
import json
from dotenv import load_dotenv
from pathlib import Path


URL = "https://sandbox.zenodo.org/api/deposit/depositions"


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

    exp_folders = sorted([
        p for p in dataset_dir.iterdir()
        if p.is_dir() and list(p.glob("*_trajectories.csv"))
    ])

    if not exp_folders:
        print(f"No experiments found (subfolders with *_trajectories.csv) in: {dataset_dir}")
        exit(1)

    print(f"Experiments found: {len(exp_folders)}")

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
        exit(1)

    n_fail = 0

    for folder in exp_folders:
        exp_name = folder.name

        csv_files = list(folder.glob("*_trajectories.csv"))
        meta_files = list(folder.glob("*_metadata.json"))

        if not csv_files:
            print(f"No CSV found in {exp_name}, skipping.")
            n_fail += 1
            continue

        csv_path = csv_files[0]
        csv_name = csv_path.name
        csv_url = f"{data_url}/{csv_name}"

        with open(csv_path, "rb") as fp:
            r_file = requests.put(csv_url, data=fp, headers=file_headers)

        if r_file.status_code in [200, 201]:
            pass
        else:
            print(f"Error uploading CSV {csv_name}: {r_file.text}")
            n_fail += 1
            continue

        if meta_files:
            meta_path = meta_files[0]
            meta_name = meta_path.name
            meta_url = f"{data_url}/{meta_name}"

            with open(meta_path, "rb") as fp:
                r_meta = requests.put(meta_url, data=fp, headers=file_headers)

            if r_meta.status_code in [200, 201]:
                pass
            else:
                print(f"Error uploading metadata {meta_name}: {r_meta.text}")


    print(f"\nUploaded files: {n_fail} failures")

    r_metadata = requests.put(f"{URL}/{data_id}", headers=json_headers, json=metadata)
    if r_metadata.status_code == 200:
        print("Global metadata saved successfully.")
    else:
        print(f"Error updating global metadata: {r_metadata.text}")
        exit(1)

    r_publication = requests.post(f"{URL}/{data_id}/actions/publish", headers=json_headers)
    if r_publication.status_code == 202:
        print("\nDeposit officially published on Zenodo Sandbox.")
        print(f"Web link: {r_publication.json().get('links', {}).get('html', 'Not available')}")
    else:
        print(f"Error publishing: {r_publication.text}")


if __name__ == "__main__":
    run()