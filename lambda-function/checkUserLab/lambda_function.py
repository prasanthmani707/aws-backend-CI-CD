import boto3
import json
from auth_utils import get_email_from_event

dynamodb = boto3.client("dynamodb")

TABLE_NAME = "ManageEC2Instances"
WALLET_TABLE = "UserWallet"
CREDIT_TABLE = "Users_Credits_Creditbased"


# -------------------------------------------------
# Parse environment list from DynamoDB format
# -------------------------------------------------
def parse_environment(env_raw):
    env_list = []

    for env in env_raw:
        if "M" in env:
            env_map = env["M"]
            env_entry = {}

            for key, value in env_map.items():
                if "S" in value:
                    env_entry[key] = value["S"]
                elif "BOOL" in value:
                    env_entry[key] = value["BOOL"]
                elif "N" in value:
                    env_entry[key] = float(value["N"])
                elif "NULL" in value:
                    env_entry[key] = None
                elif "L" in value:
                    env_entry[key] = [v.get("S") for v in value["L"] if "S" in v]
                elif "M" in value:
                    env_entry[key] = value["M"]

            env_list.append(env_entry)

    return env_list


# -------------------------------------------------
# Check if user has any lab in 3 tables
# -------------------------------------------------
def check_has_lab(email):

    # 1️⃣ Check ManageEC2Instances
    ec2_response = dynamodb.scan(
        TableName=TABLE_NAME,
        FilterExpression="begins_with(UserEmail, :email)",
        ExpressionAttributeValues={
            ":email": {"S": email}
        }
    )

    if ec2_response.get("Items"):
        return True

    # 2️⃣ Check userwallet
    wallet_response = dynamodb.query(
        TableName=WALLET_TABLE,
        KeyConditionExpression="user_email = :email",
        ExpressionAttributeValues={
            ":email": {"S": email}
        }
    )

    if wallet_response.get("Items"):
        return True

    # 3️⃣ Check user_wallet_creditbased
    credit_response = dynamodb.scan(
        TableName=CREDIT_TABLE,
        FilterExpression="email_id = :email",
        ExpressionAttributeValues={
            ":email": {"S": email}
        }
    )

    if credit_response.get("Items"):
        return True

    return False


# -------------------------------------------------
# Lambda Handler
# -------------------------------------------------
def lambda_handler(event, context):

    print("📩 Event received:", event)

    try:
        body = json.loads(event.get("body") or "{}")
        email = body.get("email")
        # email, error = get_email_from_event(event)
        #     print(f"email id : {email}")

        # if error:
        #     return error

        # =========================================================
        # CASE 1: NO EMAIL → FETCH ALL USERS
        # =========================================================
        if not email:

            print("📦 Fetching all users")

            all_users = {}
            scan_kwargs = {"TableName": WALLET_TABLE}

            while True:

                wallet_response = dynamodb.scan(**scan_kwargs)
                items = wallet_response.get("Items", [])

                for item in items:

                    user_email = item.get("user_email", {}).get("S")

                    if not user_email:
                        continue

                    if user_email not in all_users:
                        all_users[user_email] = {
                            "hasLab": check_has_lab(user_email),
                            "noEnvironment": 0,
                            "walletDetails": []
                        }

                    env_raw = item.get("environment", {}).get("L", [])
                    env_list = parse_environment(env_raw)

                    all_users[user_email]["noEnvironment"] += len(env_list)

                    all_users[user_email]["walletDetails"].append({
                        "email": user_email,
                        "id": item.get("id", {}).get("S"),
                        "name": item.get("name", {}).get("S"),
                        "course_id": item.get("course_id", {}).get("S"),
                        "premium_bundle_lab": item.get("premium_bundle_lab", {}).get("BOOL", False),
                        "environment": env_list
                    })

                if "LastEvaluatedKey" in wallet_response:
                    scan_kwargs["ExclusiveStartKey"] = wallet_response["LastEvaluatedKey"]
                else:
                    break

            return {
                "statusCode": 200,
                "body": json.dumps(all_users)
            }

        # =========================================================
        # CASE 2: EMAIL PROVIDED → FETCH USER DETAILS
        # =========================================================

        print("🔍 Checking lab access for:", email)

        has_lab = check_has_lab(email)

        wallet_details = []

        wallet_response = dynamodb.query(
            TableName=WALLET_TABLE,
            KeyConditionExpression="user_email = :email",
            ExpressionAttributeValues={
                ":email": {"S": email}
            }
        )

        for item in wallet_response.get("Items", []):

            env_raw = item.get("environment", {}).get("L", [])
            env_list = parse_environment(env_raw)

            wallet_details.append({
                "email": item.get("user_email", {}).get("S"),
                "id": item.get("id", {}).get("S"),
                "name": item.get("name", {}).get("S"),
                "course_id": item.get("course_id", {}).get("S"),
                "premium_bundle_lab": item.get("premium_bundle_lab", {}).get("BOOL", False),
                "environment": env_list
            })

        return {
            "statusCode": 200,
            "body": json.dumps({
                "hasLab": has_lab,
                "walletDetails": wallet_details
            })
        }

    except Exception as e:

        print("❌ Error:", str(e))

        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }