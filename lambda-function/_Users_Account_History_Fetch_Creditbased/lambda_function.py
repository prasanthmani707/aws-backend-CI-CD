import json
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
from auth_utils import get_email_from_event

dynamo = boto3.resource('dynamodb')
table = dynamo.Table('Users_Credits_History_Creditbased')

def decimal_to_native(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    if isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    return obj

def lambda_handler(event, context):
    email_id, error = get_email_from_event(event)
    print(f"email id : {email_id}")

    if error:
        return error

    try:
        email = email_id

        response = table.query(
            KeyConditionExpression=Key('email_id').eq(email),
            ScanIndexForward=False  # newest first
        )

        items = decimal_to_native(response.get('Items', []))

        return {
            'statusCode': 200,
            'body': json.dumps(items)
        }

    except Exception as e:
        print("Error:", e)
        return {
            'statusCode': 500,
            'body': json.dumps(str(e))
        }
