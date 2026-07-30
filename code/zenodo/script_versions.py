# Script to create a new version of a deposit in Zenodo
# First test, creation of a .txt for document versioning instead of taking it from a folder
# Json is not updated
# Old ID used

import requests
import os
from dotenv import load_dotenv

URL = "https://sandbox.zenodo.org/api/deposit/depositions"

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

# ID of the published original deposit
ORIGINAL_DEPOSIT_ID = "570557"

try:
    version_url = f"{URL}/{ORIGINAL_DEPOSIT_ID}/actions/newversion"
    r = requests.post(version_url, headers=json_headers)
    
    print(f"Server status code: {r.status_code}")
    
    if r.status_code == 201:
        print("New version successfully generated.")
        data = r.json()
        new_draft_url = data['links']['latest_draft']
        
        # We make a GET request to obtain the data (ID and bucket) of this new draft
        r_details = requests.get(new_draft_url, headers=json_headers)
        new_deposit_data = r_details.json()
        new_id = new_deposit_data['id']
        new_bucket = new_deposit_data['links']['bucket']
        
        print(f"New draft deposit created with ID: {new_id}")
        
        draft_files_url = f"{URL}/{new_id}/files"
        r_files = requests.get(draft_files_url, headers=json_headers)
        
        if r_files.status_code == 200:
            inherited_files = r_files.json()
            for old_file in inherited_files:
                file_id = old_file['id']
                delete_file_url = f"{URL}/{new_id}/files/{file_id}"
                r_del = requests.delete(delete_file_url, headers=json_headers)
                if r_del.status_code == 204:
                    print(f"Inherited file correctly deleted from the draft.")
        
        new_file = "new_file.txt"
        with open(new_file, "wb") as f:
            f.write(b"Test content for Zenodo Sandbox.")

        upload_url = f"{new_bucket}/{new_file}"

        with open(new_file, "rb") as fp:
            r_file = requests.put(upload_url, data=fp, headers=file_headers)

        if r_file.status_code in [200, 201]:
            print("File uploaded successfully to the bucket.")
        else:
            print(f"Error uploading file: {r_file.text}")
            exit(1)
            
        r_publication = requests.post(f"{URL}/{new_id}/actions/publish", headers=json_headers)
        if r_publication.status_code == 202:
            print("Deposit officially published on Zenodo Sandbox.")
            print(f"Web link: {r_publication.json().get('links', {}).get('html', 'Not available')}")
        else:
            print(f"Error publishing: {r_publication.text}")
                    
    else:
        print(f"The server rejected the versioning request: {r.text}")
        exit(1)

except Exception as e:
    print(f"Unexpected error: {e}")
    exit(1)