#!/usr/bin/env python3
"""One-time script to upload CAD input images to Google Drive using your personal Google account.

Run once:
    python upload_images_to_drive.py

It will open a browser for Google OAuth consent, upload all 20 PNG images to your
Drive folder, make them publicly viewable, and save image IDs to:
    credentials/drive_image_ids.json

The sheets report will then automatically use those IDs for =IMAGE() formulas.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DRIVE_FOLDER_ID = "1AEqHZziZfVO2W_q3RvVcuBeaxfru-LtR"
IMAGE_DIRS = [
    Path("data/images/manufacturing"),
    Path("data/images/construction"),
]
OUTPUT_FILE = Path("credentials/drive_image_ids.json")
TOKEN_FILE = Path("credentials/oauth_token.json")

# You need an OAuth 2.0 client secrets file.
# Download it from: Google Cloud Console → APIs & Services → Credentials
#   → Create Credentials → OAuth client ID → Desktop app → Download JSON
# Save it as: credentials/oauth_client_secrets.json
CLIENT_SECRETS = Path("credentials/oauth_client_secrets.json")


def main() -> None:
    if not CLIENT_SECRETS.exists():
        print(
            f"\n[ERROR] OAuth client secrets not found at: {CLIENT_SECRETS}\n\n"
            "To fix:\n"
            "  1. Go to https://console.cloud.google.com/apis/credentials\n"
            "  2. Click 'Create Credentials' → 'OAuth client ID'\n"
            "  3. Choose 'Desktop app', name it anything, click Create\n"
            "  4. Click the download icon → save as credentials/oauth_client_secrets.json\n"
            "  5. Re-run this script\n"
        )
        return

    # Load or create OAuth token
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.parent.mkdir(exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())

    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    # Load existing IDs to avoid re-uploading
    existing: dict[str, str] = {}
    if OUTPUT_FILE.exists():
        existing = json.loads(OUTPUT_FILE.read_text())

    image_ids: dict[str, str] = dict(existing)

    all_images = [p for d in IMAGE_DIRS for p in sorted(d.glob("*.png")) if d.exists()]
    print(f"Found {len(all_images)} images to upload")

    for img_path in all_images:
        name = img_path.name
        if name in image_ids:
            print(f"  SKIP (already uploaded): {name} → {image_ids[name]}")
            continue

        print(f"  Uploading: {name} ...", end=" ", flush=True)
        try:
            # Check if already exists in Drive folder
            q = f"name='{name}' and '{DRIVE_FOLDER_ID}' in parents and trashed=false"
            listed = service.files().list(q=q, fields="files(id)", pageSize=1).execute()
            if listed.get("files"):
                file_id = listed["files"][0]["id"]
                print(f"exists ({file_id})")
            else:
                meta = {"name": name, "parents": [DRIVE_FOLDER_ID]}
                media = MediaFileUpload(str(img_path), mimetype="image/png", resumable=False)
                created = service.files().create(body=meta, media_body=media, fields="id").execute()
                file_id = created["id"]
                print(f"uploaded ({file_id})")

            # Make publicly viewable
            try:
                service.permissions().create(
                    fileId=file_id,
                    body={"type": "anyone", "role": "reader"},
                ).execute()
            except Exception:
                pass

            image_ids[name] = file_id
        except Exception as exc:
            print(f"FAILED: {exc}")

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(image_ids, indent=2))
    print(f"\nSaved {len(image_ids)} image IDs to {OUTPUT_FILE}")
    print("Now re-run the sheets export to embed thumbnails.")


if __name__ == "__main__":
    main()
