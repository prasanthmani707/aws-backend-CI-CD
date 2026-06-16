import boto3
import math
from datetime import datetime, timedelta, timezone
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
instance_table = dynamodb.Table('instance_registry_creditbased')
User_credits_account_table = dynamodb.Table('Users_Credits_Creditbased') 
print("TABLE NAME:", User_credits_account_table.table_name)

def update_expiry_in_db(email, expiry_date):
    print("👉 Function called with:", email, expiry_date)

    try:
        expiry_str = expiry_date.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        response = User_credits_account_table.update_item(
            Key={
                "email_id": email
            },
            UpdateExpression="SET #exp = :exp, #updated = :updated",
            ExpressionAttributeNames={
                "#exp": "expire_at",
                "#updated": "cb_last_updated"
            },
            ExpressionAttributeValues={
                ":exp": expiry_str,
                ":updated": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            },
            ReturnValues="ALL_NEW"
        )

        print(response["Attributes"])

        print(f"✅ Expiry updated in DB for {email}: {expiry_str}")

    except Exception as e:
        print(f"❌ Failed to update expiry in DB for {email}: {str(e)}")
def fetch_instance_by_email(email):
    all_instances = []
    response = instance_table.query(
        IndexName='state-email_id-index',  # 👈 your new index
        KeyConditionExpression=
            Key('state').eq('stopped') & Key('email_id').eq(email)
    )

    all_instances.extend(response.get('Items', []))

    while 'LastEvaluatedKey' in response:
        response = instance_table.query(
            IndexName='state-email_id-index',
            KeyConditionExpression=
                Key('state').eq('stopped') & Key('email_id').eq(email),
            ExclusiveStartKey=response['LastEvaluatedKey']
        )
        all_instances.extend(response.get('Items', []))
    return all_instances

def remove_expiry_from_db(email):
    try:
        response = User_credits_account_table.update_item(
            Key={
                "email_id": email
            },
            # ✅ REMOVE attribute instead of setting null
            UpdateExpression="REMOVE expire_at SET cb_last_updated = :updated",
            ExpressionAttributeValues={
                ":updated": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
            },
            ReturnValues="UPDATED_NEW"
        )

        print(f"✅ Expiry removed for {email}")
        print("Updated attributes:", response.get("Attributes"))

    except Exception as e:
        print(f"❌ Failed to remove expiry for {email}: {str(e)}")


