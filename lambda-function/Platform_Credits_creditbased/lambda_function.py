import json
import boto3
from decimal import Decimal 
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from datetime import datetime
from get_backend_credits import get_backend_credits

# AWS clients
dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

# Tables
instance_table = dynamodb.Table("instance_registry_creditbased")
wallet_table = dynamodb.Table("Users_Credits_Creditbased")

# Other Lambdas
HISTORY_LAMBDA_NAME = "history_tracker_creditbased"

PLATFORM_credits = get_backend_credits()
print(f"platform credits {PLATFORM_credits}")

def lambda_handler(event, context):

    processed_users = set()
    results = []

    now = datetime.utcnow().isoformat()


    # time complexcity was O(K1) hash lookup
    # ---- GET RUNNING INSTANCES ----
    running_response = instance_table.query(
        IndexName = "platform_credits",
        KeyConditionExpression=Key("state").eq("running")
    )
    # time complexcity was O(K2) hash lookup
    # ---- GET STOPPED INSTANCES ----
    stopped_response = instance_table.query(
        IndexName = "platform_credits",
        KeyConditionExpression=Key("state").eq("stopped")
    )
    # O(k1 +k2) Array/List concatenation
    items = running_response.get("Items", []) + stopped_response.get("Items", [])
    
    # n = k1 +k2 complexity O(n)
    for item in items:

        email_id = item.get("email_id")
        # set data structure using time was O(1)
        if not email_id:
            print(f"⚠️ Skipping item with missing email_id: {item}")
            continue

        email_id = str(email_id).strip()

        if not email_id:
            print(f"⚠️ Skipping empty email after strip: {item}")
            continue

        if email_id in processed_users:
            continue
        try:
            # in thuis time  DSA was hash table time was O(1)
            # ---- ATOMIC WALLET UPDATE ----
            response = wallet_table.update_item(
                Key={"email_id": email_id},
                UpdateExpression="""
                    SET previous_credits = if_not_exists(current_credits, :zero),
                        current_credits = if_not_exists(current_credits, :zero) - :Credits,
                        cb_last_updated = :now
                """,
                ConditionExpression="""
                    attribute_not_exists(current_credits) OR current_credits >= :Credits
                """,
                ExpressionAttributeValues={
                    ":Credits": Decimal(str(PLATFORM_credits)),
                    ":zero": Decimal("0"),
                    ":now": now
                },
                ReturnValues="UPDATED_NEW"
            )

            prev_credits = response["Attributes"]["previous_credits"]
            curr_credits = response["Attributes"]["current_credits"]


            # ---- RECORD FOR HISTORY ----
            record_out = {
                "email_id": email_id,
                "Credits": float(PLATFORM_credits),
                "credits_before": float(prev_credits),
                "credits_after": float(curr_credits),
                "source": "platform_credits",
                "status": "SUCCESS",
                "updated_time": now
            }

            results.append(record_out)

            print(f"✅ Platform fee deducted {email_id}: {prev_credits} → {curr_credits}")

        except ClientError as e:

            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                print(f"❌ Insufficient credits for {email_id}")

            else:
                raise

        processed_users.add(email_id)

    # ---- SEND HISTORY RECORDS ----
    if results:

        payload = json.dumps({"records": results}).encode("utf-8")

        lambda_client.invoke(
            FunctionName=HISTORY_LAMBDA_NAME,
            InvocationType="Event",
            Payload=payload
        )

        print(f"🚀 Sent {len(results)} records to history lambdas")

    else:
        print("ℹ️ No wallet updates")

    return {
        "status": "processed",
        "records": len(results)
    }