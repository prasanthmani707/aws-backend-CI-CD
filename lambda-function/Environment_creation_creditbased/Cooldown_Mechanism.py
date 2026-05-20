import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta

dynamodb = boto3.resource("dynamodb")
status_table = dynamodb.Table("User_environment_history_creditbased")

def Cooldown_Mechanism(usermail):
    response = status_table.query(
        KeyConditionExpression=Key("email_id").eq(usermail)
    )

    items = response.get("Items", [])
    
    if not items:
        print("No items found → allowing first trigger")
        return True

    # Filter out items that don't have 'created_at' field
    items_with_timestamp = [i for i in items if i.get("created_at")]

    if not items_with_timestamp:
        print("No items with created_at found → allowing trigger")
        return True

    latest_item = sorted(
        items_with_timestamp,
        key=lambda x: x.get("created_at", ""),
        reverse=True
    )[0]

    latest_created_at = latest_item["created_at"]

    latest_time = datetime.fromisoformat(latest_created_at)
    print("Latest:", latest_time)

    now_time = datetime.utcnow()
    print("Now:", now_time)

    time_diff = now_time - latest_time
    print("Difference:", time_diff)

    return time_diff > timedelta(minutes=2)