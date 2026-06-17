import jwt
import datetime
import json
import urllib.request
import time
import os
import boto3




GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
def verify_google_token(token_id):
    GOOGLE_ISSURES = "https://accounts.google.com"
    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token_id}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        aud = data.get("aud")
        iss = data.get("iss")
        exp = data.get("exp")

        print("GOOGLE_CLIENT_ID =", GOOGLE_CLIENT_ID)
        print("TOKEN AUD =", aud)

        if aud != GOOGLE_CLIENT_ID:
            print("Invalid client ID")
            return None
        if iss != GOOGLE_ISSURES:
            print("Invalid issuer")
            return None
        if int(exp) < int(time.time()):
            print("Token expired")
            return None
        return data
    except Exception as e:
        print(f"Google verification failed: {e}")
        return None

