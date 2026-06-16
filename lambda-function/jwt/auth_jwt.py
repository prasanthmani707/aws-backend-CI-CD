import jwt
import json
import datetime

def create_jwt(user_data):

    # read private key
    with open("private.pem", "r") as f:
        private_key = f.read()

    email = (
        user_data.get("email")
        or user_data.get("Email")
        or user_data.get("emailId")
        or user_data.get("email_id")
    )
    print(f"user email id {email}")
    payload = {

    "email": email,

    "name": (
        user_data.get("profile", {}).get("first_name")
    ),

    "address": (
        user_data.get("profile", {}).get("address")
    ),

    "plan": (
        user_data.get("current_plan")
        or user_data.get("plan")
    ),

    "plan_status": (
        user_data.get("subscriptions", [{}])[0].get("status")
        if user_data.get("subscriptions")
        else None
    ),

    "phone_number": (
        user_data.get("profile", {}).get("phone_number")
    ),

        # MUST match API Gateway
        "iss": "https://my-auth-jwks.s3.amazonaws.com/",
        "aud": "my-api",

        # expiry
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }

    # 🔥 ADD HEADER HERE
    token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={
            "kid": "Tlhd__xUb2k-GGN3k5_IaQBjkce4t6XzHYELNOaKiws"   # 👈 VERY IMPORTANT
        }
    )

    return token