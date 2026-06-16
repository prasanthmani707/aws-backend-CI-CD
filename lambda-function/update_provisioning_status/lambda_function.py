import json
import boto3
import time
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ProvisioningStatus')

def lambda_handler(event, context):
    email = event.get('email')
    build_id = event.get('build_id')        # must provide sort key
    status = event.get('status')            # optional
    instance_id = event.get('instance_id')  # optional

    if not email or not build_id:
        return {"statusCode": 400, "body": "Missing email or build_id"}

    update_expr = []
    expr_attr_values = {}
    expr_attr_names = {}

    # ---------- Existing logic (unchanged) ----------
    if instance_id:
        update_expr.append(
            "instance_ids = list_append(if_not_exists(instance_ids, :empty_list), :ids)"
        )
        expr_attr_values[":ids"] = [instance_id]
        expr_attr_values[":empty_list"] = []

    if status:
        update_expr.append("#s = :status")
        expr_attr_values[":status"] = status
        expr_attr_names["#s"] = "status"
    # ------------------------------------------------

    # ---------- NEW: started_at & ttl (safe add) -----
    started_at = datetime.now(timezone.utc).isoformat()
    ttl = int(time.time()) + (5 * 24 * 60 * 60)  # 5 days

    update_expr.append(
        "started_at = if_not_exists(started_at, :started_at)"
    )
    update_expr.append(
        "#ttl = if_not_exists(#ttl, :ttl)"
    )

    expr_attr_values[":started_at"] = started_at
    expr_attr_values[":ttl"] = ttl
    expr_attr_names["#ttl"] = "ttl"
    # ------------------------------------------------

    if not update_expr:
        return {"statusCode": 400, "body": "Nothing to update"}

    kwargs = {
        "Key": {
            "email": email,
            "build_id": build_id
        },
        "UpdateExpression": "SET " + ", ".join(update_expr),
        "ExpressionAttributeValues": expr_attr_values
    }

    if expr_attr_names:
        kwargs["ExpressionAttributeNames"] = expr_attr_names

    table.update_item(**kwargs)

    return {
        "statusCode": 200,
        "body": json.dumps("✅ DynamoDB updated successfully.")
    }
