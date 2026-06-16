import json
import boto3
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
from botocore.exceptions import ClientError


# DynamoDB
dynamodb = boto3.resource("dynamodb")
ledger_table = dynamodb.Table("Users_Credits_History_Creditbased")


def store_ledger_entry(
    email_id,
    txn_id,
    Credits,
    discount_credits,
    original_credits,
    credits_before,
    credits_after,
    source,
    created_at,
    used_time=None,
    instance_id=None,
    instance_name=None
):
    """Store ledger entry with dynamic txn_type based on source"""
    try:
        # 🔥 DYNAMIC txn_type logic:
        if source in ["compute", "storage", "platform_fee"]:
            txn_type = "DEDUCT"
        else:
            txn_type = "PAY"

        item = {
            "email_id": email_id,        # PK
            "tnx_id": txn_id,            # SK
            "txn_type": txn_type,
            "Credits": Credits,
            "discount_credits": discount_credits,
            "original_credits": original_credits,
            "credits_before": credits_before,
            "credits_after": credits_after,
            "source": source,
            "created_at": created_at
        }

        # Only add optional fields if they exist
        if instance_name:
            item["instance_name"] = instance_name

        if instance_id:
            item["instance_id"] = instance_id

        if used_time:
            item["used_time"] = used_time

        ledger_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(tnx_id)"
        )

        print(f"✅ [{txn_type}] Ledger stored | {email_id} | {credits_before} → {credits_after}")
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            print(f"⚠️ Duplicate ledger ignored: {txn_id}")
            return True
        else:
            print(f"❌ Ledger storage failed: {e}")
            raise


def lambda_handler(event, context):
    print("🔔 Received Event:")
    print(json.dumps(event, indent=2))

    records = event.get("records", [])
    if not records:
        print("ℹ️ No records received")
        return {"status": "NO_RECORDS"}

    for rec in records:
        if rec.get("status") != "SUCCESS":
            continue

        email_id = rec["email_id"]

        Credits = Decimal(str(rec.get("Credits", 0)))
        original_credits = Decimal(str(rec.get("original_credits", Credits)))
        discount_credits = Decimal(str(rec.get("discount_credits", 0)))


        instance_id = rec.get("instance_id")
        instance_name = rec.get("instance_name")
        credits_before = Decimal(str(rec.get("credits_before", 0)))
        credits_after = Decimal(str(rec.get("credits_after", 0)))
        used_time = rec.get("used_time")
        source = rec.get("source")

        txn_id = str(rec.get("updated_time", datetime.utcnow().isoformat()))
        created_at = datetime.utcnow().isoformat()

        print(f"{used_time}")


        # Store ledger entry
        if store_ledger_entry(
            email_id,
            txn_id,
            Credits,
            discount_credits,
            original_credits,
            credits_before,
            credits_after,
            source,
            created_at,
            used_time,
            instance_id,
            instance_name
        ):
            print(f"✅ Ledger entry written | {email_id} | {credits_before} → {credits_after}")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Storage ledger processed"})
    }