# Script to list and delete Zenodo depositions
# Published depositions cannot be deleted, only drafts can

import argparse
import os
import requests
from dotenv import load_dotenv

URL = "https://sandbox.zenodo.org/api/deposit/depositions"

load_dotenv()
TOKEN = os.getenv("Token_Zenodo_Sandbox")
if not TOKEN:
    print("The environment variable 'TOKEN' is not configured.")
    exit(1)

HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def list_depositions(base_url):
    params = {"page": 1, "size": 100}
    r = requests.get(base_url, headers=HEADERS, params=params)
    if r.status_code != 200:
        print(f"Error listing depositions: {r.text}")
        return
    depositions = r.json()
    if not depositions:
        print("No depositions found.")
        return
    for i in depositions:
        state = i.get("state", "unknown")
        metadata = i.get("metadata", {})
        title = metadata.get("title", "Untitled")
        print(f"  ID: {i['id']} | State: {state} | Title: {title}")


def delete_deposition(base_url, deposition_id):
    r = requests.delete(f"{base_url}/{deposition_id}", headers=HEADERS)
    if r.status_code == 204:
        print(f"Deposition {deposition_id} deleted successfully.")
    else:
        print(f"Error deleting deposition {deposition_id}: {r.text}")


def main():
    parser = argparse.ArgumentParser(description="List and delete Zenodo depositions")
    parser.add_argument("--list", action="store_true", help="List depositions")
    parser.add_argument("--delete", type=str, default=None, help="ID of the deposition to delete")
    args = parser.parse_args()

    print(f"Using: {URL}")

    if args.list:
        list_depositions(URL)
    elif args.delete:
        confirm = input(f"Are you sure you want to delete deposition {args.delete}? (yes/no): ")
        if confirm.strip().lower() == "yes":
            delete_deposition(URL, args.delete)
        else:
            print("Deletion canceled.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()