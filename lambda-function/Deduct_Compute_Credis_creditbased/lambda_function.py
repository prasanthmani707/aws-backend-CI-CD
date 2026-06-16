import json
import boto3
from decimal import Decimal
from datetime import datetime
from botocore.exceptions import ClientError
from community_member_check import apply_member_discount
dynamodb = boto3.resource("dynamodb")
wallet_table = dynamodb.Table("Users_Credits_Creditbased")
lambda_client = boto3.client("lambda")

HISTORY_LAMBDA_NAME = "history_tracker_creditbased"
INSTANCE_TRACKER_LAMBDA_NAME = "Instance_tracker_creditbased"


def lambda_handler(event, context):
    print("🔥 EVENT RECEIVED")
    print(json.dumps(event))

    results = []

    for record in event.get("Records", []):

        #  Validate source
        if record.get("eventSource") != "aws:dynamodb":
            print("⏭ Not DynamoDB event")
            continue

        if record.get("eventName") != "MODIFY":
            print("⏭ Not MODIFY event")
            continue

        new_image = record["dynamodb"].get("NewImage")
        if not new_image:
            print("⏭ No NewImage")
            continue

        #  State check
        state = new_image.get("state", {}).get("S", "").lower()
        print("DEBUG → state:", state)


        # Cost check
        total_credits = new_image.get("session_total_credits", {}).get("N")
        if not total_credits:
            print("⏭ No total_credits")
            continue

        Credits = Decimal(total_credits)
        email_id = new_image.get("email_id", {}).get("S")
        
        if not email_id:
            print("⏭ No email_id")
            continue

        instance_id = new_image.get("instance_id", {}).get("S", "UNKNOWN")
        instance_name = new_image.get("instance_name", {}).get("S", "UNKNOWN")
        used_time = new_image.get("session_used_time_seconds", {}).get("N")
        updated_time = datetime.utcnow().isoformat()
        print(f"💰 Charging user_credit_account → {email_id}, Credits={Credits}")
        print(f"💰 Calculated storage credits: {Credits}")
        original_credits = Credits
        Credits, discount_credits = apply_member_discount(email_id, Credits)

        print(f"Original credits: {original_credits}, Discount applied: {discount_credits}, Final Credits: {Credits}")
        print(f"Credits to pay: {Credits}")

        try:
            # 4️⃣ WALLET UPDATE
            response = wallet_table.update_item(
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

            print(f"✅ Wallet updated: {prev_credits} → {curr_credits}")

            results.append({
                "email_id": email_id,
                "instance_id": instance_id,
                "instance_name": instance_name,
                "original_credits": float(original_credits),   # <-- original
                "discount_credits": float(discount_credits),  
                "Credits": float(Credits),
                "used_time": int(used_time) if used_time else 0,
                "credits_before": float(prev_credits),
                "credits_after": float(curr_credits),
                "source": "compute",
                "status": "SUCCESS",
                "updated_time": updated_time
            })

        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                print(f"⚠️ Insufficient Credits for {email_id}")
            else:
                print("❌ DynamoDB error", e)
                raise

    # 5️⃣ Invoke ledger
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
        print("ℹ️ No credits acoount updates done")

    return {"status": "ok"}
