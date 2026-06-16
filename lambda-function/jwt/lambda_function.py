import json

from trainer_central import create_user
from checkuser import check_user
from auth_jwt import create_jwt
from verify_google_token import verify_google_token
from update_db import update_db
from dotenv import load_dotenv
load_dotenv() 


def lambda_handler(event, context):

    path = event.get("rawPath") or event.get("path")

    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method")
        or event.get("httpMethod")
    )

    print("=" * 80)
    print(f"REQUEST RECEIVED | PATH={path} | METHOD={method}")
    print("=" * 80)

    # ==========================================================
    # CHECK USER / LOGIN
    # ==========================================================
    if path == "/user_profile/checkuser" and method == "POST":

        print("LOGIN FLOW STARTED")

        body = json.loads(event.get("body") or "{}")

        token_id = body.get("token")

        if not token_id:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "message": "Google token is required"
                })
            }

        data = verify_google_token(token_id)

        if not data:
            print("Google token verification failed")

            return {
                "statusCode": 401,
                "body": json.dumps({
                    "message": "Invalid token"
                })
            }

        email_id = data.get("email")

        print(f"Authenticated user: {email_id}")

        user_result = check_user(email_id)

        if user_result is False or (isinstance(user_result, dict) and user_result.get("status") == "error"):

            print(f"User check failed: {user_result}")

            return {
                "statusCode": 404 if user_result is False else 500,
                "body": json.dumps({
                    "message": "User not found" if user_result is False else f"Database error: {user_result.get('message')}"
                })
            }

        if "body" in user_result:
            user_result = json.loads(user_result["body"])

        user_data = user_result.get("data") or user_result
        if isinstance(user_data, dict):
            user_data["picture"] = user_data.get("picture") or data.get("picture") or ""
            db_discord = user_data.get("discord") or {}
            user_data["discord"] = {
                "discord_linked": db_discord.get("discord_linked", False),
                "discord_username": db_discord.get("discord_username", ""),
                "discord_user_id": db_discord.get("discord_user_id", ""),
                "joined_dc_community_group": db_discord.get("joined_dc_community_group", False),
                "discord_dm_verified": db_discord.get("discord_dm_verified", False)
            }

        token = create_jwt(user_data)

        print("JWT created successfully")

        response_body = {
            "message": "login success",
            "user": user_data,
            "source": user_result.get("source")
        }

        return {
            "statusCode": 200,
            "headers": {
                "Set-Cookie": (
                    f"token={token}; "
                    f"HttpOnly; "
                    f"Path=/; "
                    f"Max-Age=3600; "
                    f"Secure; "
                    f"SameSite=Strict"
                )
            },
            "body": json.dumps(response_body)
        }

    # ==========================================================
    # USER ADD
    # ==========================================================
    if path == "/user_profile/useradd" and method == "POST":

        print("USER REGISTRATION FLOW STARTED")

        body = json.loads(event.get("body") or "{}")

        token_id = body.get("token")

        if not token_id:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "message": "Google token is required"
                })
            }

        data = verify_google_token(token_id)

        if not data:

            print("Google token verification failed")

            return {
                "statusCode": 401,
                "body": json.dumps({
                    "message": "Invalid token"
                })
            }

        email_id = data.get("email")

        print(f"Creating user for email: {email_id}")

        create_user_response = create_user(
            email_id,
            body.get("name")
        )

        print("Zoho user creation response:")
        print(create_user_response)

        db_response = update_db(
            email_id,
            body
        )

        print("Database create/update response:")
        print(db_response)

        user_result = check_user(email_id)

        if user_result is False or (isinstance(user_result, dict) and user_result.get("status") == "error"):

            print(f"User creation verification failed: {user_result}")

            return {
                "statusCode": 500,
                "body": json.dumps({
                    "message": "User creation failed" if user_result is False else f"Database error: {user_result.get('message')}"
                })
            }

        if "body" in user_result:
            user_result = json.loads(user_result["body"])

        user_data = user_result.get("data") or user_result
        if isinstance(user_data, dict):
            user_data["picture"] = user_data.get("picture") or data.get("picture") or ""
            db_discord = user_data.get("discord") or {}
            user_data["discord"] = {
                "discord_linked": db_discord.get("discord_linked", False),
                "discord_username": db_discord.get("discord_username", ""),
                "discord_user_id": db_discord.get("discord_user_id", ""),
                "joined_dc_community_group": db_discord.get("joined_dc_community_group", False),
                "discord_dm_verified": db_discord.get("discord_dm_verified", False)
            }

        token = create_jwt(user_data)

        print("User registration completed successfully")

        return {
            "statusCode": 200,
            "headers": {
                "Set-Cookie": (
                    f"token={token}; "
                    f"HttpOnly; "
                    f"Path=/; "
                    f"Max-Age=3600; "
                    f"Secure; "
                    f"SameSite=Strict"
                )
            },
            "body": json.dumps({
                "message": "user added successfully",
                "user": user_data
            })
        }

    # ==========================================================
    # DEFAULT ROUTE
    # ==========================================================
    print(f"ROUTE NOT FOUND | PATH={path}")

    return {
        "statusCode": 404,
        "body": json.dumps({
            "message": "Route not found"
        })
    }