import boto3
import json
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key, Attr

from every_few_minute_trigger import process_running_instances
from calculate_credits import calculate_credits

# ---------------- AWS clients ----------------
ec2 = boto3.client("ec2")
dynamodb = boto3.resource("dynamodb")

table = dynamodb.Table("Compute_Credits_Creditbased")
Credits_catalog = dynamodb.Table("Credits_Rate_Creditbased")
region_type = "sa-east-1"

# ---------------- Price lookup ----------------
def get_ec2_credits_per_hour(instance_type, region):
    resource_type = f"ec2#{region_type}#{instance_type}"
    response = Credits_catalog.get_item(Key={"resource_type": resource_type})
    item = response.get("Item")
    if not item:
        return None
    return Decimal(str(item["credits_per_hour"]))


# ---------------- Lambda handler ----------------
def lambda_handler(event, context):
    now = datetime.utcnow()
    
    # Trigger from scheduler
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except Exception as e:
            print(f"Error parsing event string: {e}")
            return {"statusCode": 400, "body": "Invalid event format"}

    # If "detail" not present, assume scheduled run
    if "detail" not in event:
        return process_running_instances()

    instance_id = event["detail"]["instance-id"]
    state = event["detail"]["state"]
    region = event["region"]

    print(f"📥 Event received: {instance_id} → {state}")

    email_id = None
    per_hour_credits = None
    instance_name = "N/A"

    # ---------------- Instance metadata ----------------
    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response["Reservations"][0]["Instances"][0]
        tags = instance.get("Tags", [])

        email_id = next(
            (t["Value"].lower() for t in tags if t["Key"] == "UserEmail"), None
        )
        instance_name = next(
            (t["Value"] for t in tags if t["Key"] == "Name"), "N/A"
        )
        instance_type = instance["InstanceType"]
        per_hour_credits = get_ec2_credits_per_hour(instance_type, region)

    except Exception as e:
        print(f"⚠️ describe_instances failed: {e}")

    # ================= RUNNING =================
    if state == "running":
        table.put_item(
            Item={
                "instance_id": instance_id,
                "tnx_id": now.isoformat(),
                "instance_name": instance_name,
                "email_id": email_id,
                "state": "running",
                "start_time": now.isoformat(),
                "last_calculated_time": now.isoformat(),
                "per_hour_credits": per_hour_credits,
                "total_credits": Decimal("0"),
                "session_total_credits": Decimal("0"),
                "used_time_seconds": 0,
                "session_used_time_seconds": 0,
            }
        )
        print(f"Instance {instance_id} started")
        return {"statusCode": 200}

    # ================= STOPPED / TERMINATED =================
    elif state in ("stopped", "terminated"):

        # Find latest RUNNING session
        running_resp = table.query(
            KeyConditionExpression=Key("instance_id").eq(instance_id),
            FilterExpression=Attr("state").eq("running"),
            ScanIndexForward=False,
            Limit=1,
        )

        if not running_resp["Items"]:
            print("No running session found (already closed)")
            return {"statusCode": 200}

        running_item = running_resp["Items"][0]

        # Idempotency guard
        if "end_time" in running_item:
            print("Session already ended")
            return {"statusCode": 200}

        # ---------------- Calculate final incremental credits ----------------
        final_incremental_credits, final_seconds = calculate_credits(running_item, now)

        # Update DynamoDB with final credits and stop state
        table.update_item(
            Key={
                "instance_id": instance_id,
                "tnx_id": running_item["tnx_id"]
            },
            UpdateExpression="""
                SET total_credits = if_not_exists(total_credits, :zero) + :inc_credits,
                    session_total_credits = :inc_credits,
                    used_time_seconds = if_not_exists(used_time_seconds, :zero) + :inc_sec,
                    session_used_time_seconds = :inc_sec,
                    last_calculated_time = :now,
                    end_time = :now,
                    #st = :stopped
            """,
            ExpressionAttributeNames={
                "#st": "state"   # alias for reserved keyword 'state'
            },
            ExpressionAttributeValues={
                ":inc_credits": final_incremental_credits,
                ":inc_sec": final_seconds,
                ":now": now.isoformat(),
                ":stopped": state,  # value to store in 'state'
                ":zero": Decimal("0")
            }
        )

        print(
            f"Final credits updated for {instance_id}: {final_incremental_credits} | "
            f"User time: {final_seconds}s"
        )

        return {"statusCode": 200}