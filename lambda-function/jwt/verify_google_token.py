import jwt
import datetime
import json
import urllib.request
import time
import os
import boto3
from dotenv import load_dotenv
load_dotenv() 

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")

def verify_google_token(token_id):
    GOOGLE_ISSURES = "https://accounts.google.com"
    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token_id}"
    try:
        with urllib.request.urlopen(url, timeout =10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        raise Exception("Goole verification failed")
    aud = data.get("aud")
    iss = data.get("iss")
    exp = data.get("exp")
    
    if iss != GOOGLE_ISSURES:
        raise Exception("Invalid issuer")
    if int(exp) < int (time.time()):
        raise Exception("Token expired")
    return data
