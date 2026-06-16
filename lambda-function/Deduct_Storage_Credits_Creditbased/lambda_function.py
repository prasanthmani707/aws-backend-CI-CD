import json
import boto3
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
from botocore.exceptions import ClientError
from community_member_check import apply_member_discount

dynamodb = boto3.resource("dynamodb")
credits_table = dynamodb.Table("Users_Credits_Creditbased")

# Lambda client
lambda_client = boto3.client("lambda")

HISTORY_LAMBDA_NAME = "history_tracker_creditbased"
INSTANCE_TRACKER_LAMBDA_NAME = "Instance_tracker_creditbased"


def lambda_handler(event, context):
    print("🔔 DynamoDB Stream Event")
    print(json.dumps(event))

    results = []

    for record in event.get("Records", []):

        if record.get("eventSource") != "aws:dynamodb":
            continue

        event_name = record.get("eventName")
        if event_name not in ("MODIFY","REMOVE"):
            continue

        dynamodb_data = record.get("dynamodb", {})
        old_image = dynamodb_data.get("OldImage")
        new_image = dynamodb_data.get("NewImage")
        instance_id = ((new_image or {}).get("instance_id", {}).get("S")or (old_image or {}).get("instance_id", {}).get("S"))
        instance_name = (new_image or {}).get("instance_name", {}).get("S")
        last_duration_seconds = (new_image or {}).get("last_duration_seconds", {}).get("N")
        print(f"time duration for credits {last_duration_seconds}")
        # ---- EMAIL ID ----
        email_id = (
            (new_image or {}).get("email_id", {}).get("S")
            or (old_image or {}).get("email_id", {}).get("S")
        )
        email_id = email_id.lower()

        if not email_id:
            continue

        # ---- STORAGE CREDITS CALCULATION ----
        old_credits = Decimal(
            (old_image or {}).get("running_credits", {}).get("N", "0")
        )
        new_credits = Decimal(
            (new_image or {}).get("running_credits", {}).get("N", "0")
        )

        if event_name == "REMOVE":
            Credits = old_credits
        else:
            Credits = new_credits - old_credits

        if Credits <= 0:
            print(f"ℹ️ No storage credits change for {email_id}")
            continue

        updated_time = datetime.utcnow().isoformat()
        print(f"💰 Calculated storage credits: ${Credits}")
        original_credits = Credits  # Save the original credits before discount
        Credits, discount_credits = apply_member_discount(email_id, Credits)
        print(f"Original credits: {original_credits}, Discount applied: {discount_credits}, Final credits to charge: {Credits}")
        print(f"Credits to pay: {Credits}")
        try:
            # 🔐 ATOMIC credits UPDATE (NO IDENTITY FIELDS STORED)
            response = credits_table.update_item(
                Key={"email_id": email_id},
                UpdateExpression="""
                    SET previous_credits = current_credits,
                        current_credits = current_credits - :Credits,
                        cb_last_updated = :now
                """,
                ConditionExpression="current_credits >= :Credits",
                ExpressionAttributeValues={
                    ":Credits": Credits,
                    ":now": updated_time
                },
                ReturnValues="UPDATED_NEW"
            )

            prev_credits = response["Attributes"]["previous_credits"]
            curr_credits = response["Attributes"]["current_credits"]

            record_out = {
                "email_id": email_id,
                "instance_id": instance_id,
                "instance_name": instance_name,
                "Credits": float(Credits),
                "used_time":last_duration_seconds,
                "original_credits": float(original_credits),   # <-- original
                "discount_credits": float(discount_credits),  
                "credits_before": float(prev_credits),
                "credits_after": float(curr_credits),
                "source": "storage",
                "status": "SUCCESS",
                "updated_time": updated_time
            }
            

            print(f"✅ Storage credits deducted: {prev_credits} → {curr_credits}")
            results.append(record_out)

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                print(f"❌ Insufficient credits for {email_id}")
            else:
                raise

    # ---- INVOKE LEDGER LAMBDA ----
    if results:
        print(f"🚀 Invoking Ledger with {len(results)} successful charges")
        payload = json.dumps({"records": results}).encode("utf-8")
        lambda_name =[
            HISTORY_LAMBDA_NAME,
            INSTANCE_TRACKER_LAMBDA_NAME,
        ]
        print(f"Invoke → lambda_name: {len(lambda_name)}")
        for name in lambda_name:
            lambda_client.invoke(
                FunctionName=name,
                InvocationType="Event",
                Payload=payload,
            )
    else:
        print("ℹ️ No credits updates done")

    return {"status": "processed"}
