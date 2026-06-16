import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta


def zohosheetupdate(email_id, Credits, admin_email, reason):
    try:
        print("🔹 Zoho update start")

        # -------------------------------
        # STEP 1: GET ACCESS TOKEN
        # -------------------------------
        token_url = "https://accounts.zoho.in/oauth/v2/token"

        token_payload = urllib.parse.urlencode({
            "refresh_token": os.environ.get("ZOHO_REFRESH_TOKEN"),
            "client_id": os.environ.get("ZOHO_CLIENT_ID"),
            "client_secret": os.environ.get("ZOHO_CLIENT_SECRET"),
            "grant_type": "refresh_token"
        }).encode()

        token_request = urllib.request.Request(
            token_url,
            data=token_payload,
            method="POST"
        )

        with urllib.request.urlopen(token_request) as res:
            token_response = json.loads(res.read().decode())

        access_token = token_response.get("access_token")

        if not access_token:
            print("❌ Failed to get access token:", token_response)
            return

        print("✅ Access Token received")

        # -------------------------------
        # STEP 2: PREPARE DATA (IMPORTANT)
        # -------------------------------
        sheet_id = os.environ.get("ZOHO_SHEET_ID")
        sheetid = os.environ.get("SHEETID")

        url = f"https://sheet.zoho.in/api/v2/{sheet_id}"

        json_data = json.dumps([{
            "User Email": str(email_id),
            "Credits Added": float(Credits),
            "Reason": str(reason),
            "Admin Email": str(admin_email),
            "Timestamp": (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%d-%m-%Y %I:%M:%S %p")
        }])

        payload_dict = {
            "method": "worksheet.records.add",
            "worksheet_name": sheetid,
            "json_data": json_data
        }

        print("📦 Zoho Payload:", payload_dict)

        payload = urllib.parse.urlencode(payload_dict).encode()

        # -------------------------------
        # STEP 3: SEND REQUEST
        # -------------------------------
        request = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Zoho-oauthtoken {access_token}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            method="POST"
        )

        with urllib.request.urlopen(request) as res:
            response_data = res.read().decode()
            print("✅ Zoho Success:", response_data)

    except Exception as e:
        print("❌ Zoho Error:", str(e))