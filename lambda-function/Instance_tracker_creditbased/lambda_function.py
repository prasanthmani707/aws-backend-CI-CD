import json
import boto3
from decimal import Decimal
from datetime import datetime

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("instance_tracker_creditbased")

def lambda_handler(event, context):
    records = event.get("records", [])

    if not records:
        return {"statusCode": 400, "body": "No records found"}

    usage_date = datetime.utcnow().date().isoformat()

    for rec in records:

        if rec.get("status") != "SUCCESS":
            continue

        instance_id = rec.get("instance_id")
        instance_name = rec.get("instance_name")
        email_id = rec.get("email_id")
        source = rec.get("source")

        if not instance_id or not email_id:
            continue

        compute_credits = Decimal("0")
        storage_credits = Decimal("0")
        used_time = Decimal("0")

        Credits = Decimal(str(rec.get("Credits", 0)))

        if source == "compute":
            compute_credits = Credits
            used_time = Decimal(str(rec.get("used_time", 0)))
        elif source == "storage":
            storage_credits = Credits
        else:
            continue

        date_instance = f"{usage_date}#{instance_id}"
        updated_time = datetime.utcnow().isoformat()

        table.update_item(
            Key={
                "email_id": email_id,
                "date_instance": date_instance 
            },
            UpdateExpression="""
                SET
                    instance_id = :iid,
                    usage_date = :ud,
                    instance_name =:in,
                    compute_credits = if_not_exists(compute_credits, :zero) + :cc,
                    storage_credits = if_not_exists(storage_credits, :zero) + :sc,
                    used_time = if_not_exists(used_time, :zero) + :utime,
                    total_credits = if_not_exists(total_credits, :zero) + :tc,
                    updated_time = :updated
            """,
            ExpressionAttributeValues={
                ":iid": instance_id,
                ":ud": usage_date,
                ":in":instance_name,
                ":cc": compute_credits,
                ":sc": storage_credits,
                ":utime": used_time,
                ":tc": compute_credits + storage_credits,
                ":updated": updated_time,
                ":zero": Decimal("0")
            }
        )

    return {"statusCode": 200, "body": "Daily instance credity recorded"}