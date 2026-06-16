import boto3
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from calculate_credits import calculate_credits

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Compute_Credits_Creditbased')

def process_running_instances():
    now = datetime.utcnow()

    # Query all currently running instances
    response = table.query(
        IndexName='few_minute_trigger',  # make sure this GSI exists
        KeyConditionExpression=Key('state').eq('running')
    )

    items = response.get('Items', [])

    for item in items:
        instance_id = item['instance_id']

        # Calculate incremental credits since last calculation
        incremental_credits, incremental_seconds = calculate_credits(item, now)

        if incremental_credits == 0:
            continue  # nothing new to update

        # Update DynamoDB: cumulative + incremental fields
        table.update_item(
            Key={
                'instance_id': instance_id,
                'tnx_id': item['tnx_id']
            },
            UpdateExpression="""
                SET total_credits = if_not_exists(total_credits, :zero) + :inc_credits,
                    session_total_credits = :inc_credits,
                    used_time_seconds = if_not_exists(used_time_seconds, :zero) + :inc_sec,
                    session_used_time_seconds = :inc_sec,
                    last_calculated_time = :now
            """,
            ExpressionAttributeValues={
                ':inc_credits': incremental_credits,
                ':inc_sec': incremental_seconds,
                ':now': now.isoformat(),
                ':zero': Decimal("0")
            }
        )

        print(f"Updated running credits for {instance_id} → {incremental_credits} | "
              f"User time: {incremental_seconds}s")

    return {"statusCode": 200}