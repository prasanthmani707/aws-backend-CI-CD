import time
import os
import boto3
from safe_request import safe_request
from dotenv import load_dotenv
load_dotenv() 

# ---------------- CONFIG ----------------

BASE_URL = os.environ.get("BASE_URL")
ORG_ID = os.environ.get("ORG_ID")

ZOHO_CLIENT_ID = os.environ.get("ZOHO_CLIENT_ID")
ZOHO_CLIENT_SECRET = os.environ.get("ZOHO_CLIENT_SECRET")
ZOHO_REFRESH_TOKEN = os.environ.get("ZOHO_REFRESH_TOKEN")


TOKEN_TABLE = "Trainer-central-Oauth-token"

AWS_REGION = "us-west-2"

# ---------------- VALIDATION ----------------

required_envs = {
    "BASE_URL": BASE_URL,
    "ORG_ID": ORG_ID,
    "ZOHO_CLIENT_ID": ZOHO_CLIENT_ID,
    "ZOHO_CLIENT_SECRET": ZOHO_CLIENT_SECRET,
    "ZOHO_REFRESH_TOKEN": ZOHO_REFRESH_TOKEN,
}

for key, value in required_envs.items():
    if not value:
        raise Exception(f"{key} environment variable missing")

# ---------------- AWS ----------------

dynamodb = boto3.resource(
    "dynamodb",
    region_name=AWS_REGION
)

token_table = dynamodb.Table(TOKEN_TABLE)

# ---------------- TOKEN CONFIG ----------------

TOKEN_TYPE = "trainer-central-users"

TOKEN_LIFETIME = 3600

REFRESH_BUFFER = 10 * 60



# ---------------- TOKEN GENERATION ----------------

def generate_zoho_access_token():

    print("Generating Zoho access token")

    url = "https://accounts.zoho.in/oauth/v2/token"

    fields = {
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "refresh_token": ZOHO_REFRESH_TOKEN,
        "grant_type": "refresh_token"
    }

    data = safe_request(
        "POST",
        url,
        fields=fields,
        form_encoded=True
    )
    print("generated access token ", data)
    if "access_token" not in data:
        raise Exception(
            f"Zoho token response invalid: {data}"
        )

    return data["access_token"]

# ---------------- GET ACCESS TOKEN ----------------

def get_zoho_access_token():

    now = int(time.time())

    try:

        res = token_table.get_item(
            Key={
                "token_type": TOKEN_TYPE
            }
        )

        if "Item" in res:

            item = res["Item"]

            if item["expires_at"] > now + REFRESH_BUFFER:

                print("Using cached Zoho token")

                return item["access_token"]

    except Exception as e:

        print(f"Token read failed: {str(e)}")

    print("Refreshing Zoho token")

    token = generate_zoho_access_token()
    print("new access token generated !")
    expires_at = now + TOKEN_LIFETIME
    Item = {
        "token_type": TOKEN_TYPE,
        "access_token": token,
        "expires_at": expires_at,
        "ttl": expires_at
    }
    token_table.put_item(
        Item=Item
    )
    print("DBRecord ",Item)
    return token

# ---------------- CREATE USER ----------------

def create_user(email, username):

    access_token = get_zoho_access_token()

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }

    url = f"{BASE_URL}/api/v4/{ORG_ID}/addCourseAttendee.json"

    payload = {
        "courseAttendee": {
            "email": email,
            "firstName": username
        }
    }

    print("REQUEST URL:", url)
    print("REQUEST PAYLOAD:", payload)

    return safe_request(
        "POST",
        url,
        headers=headers,
        fields=payload
    )