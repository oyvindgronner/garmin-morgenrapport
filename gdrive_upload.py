import json
import os
import sys
from datetime import date

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

MAPPE_ID = "1_hC0owPxysECL3qLPno0AO-0ypEbI5BR"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def last_opp(json_fil: str):
    service_account_info = json.loads(os.environ["GDRIVE_SERVICE_ACCOUNT"])
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES
    )
    service = build("drive", "v3", credentials=credentials)

    filnavn = os.path.basename(json_fil)
    media = MediaFileUpload(json_fil, mimetype="application/json")

    fil = service.files().create(
        body={"name": filnavn, "parents": [MAPPE_ID]},
        media_body=media,
        fields="id, name"
    ).execute()

    print(f"✅ Lastet opp: {fil['name']} (ID: {fil['id']})")


if __name__ == "__main__":
    dato = date.today().strftime("%Y-%m-%d")
    json_fil = f"garmin_data_{dato}.json"

    if not os.path.exists(json_fil):
        print(f"Finner ikke {json_fil}")
        sys.exit(1)

    last_opp(json_fil)
