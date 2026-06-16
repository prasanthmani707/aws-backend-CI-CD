import json
import boto3
import os

dynamodb = boto3.client('dynamodb')
TABLE_NAME = os.environ.get('TABLE_NAME', 'Admin')
from auth_utils import get_email_from_event

def lambda_handler(event, context):
    print("Event:", event)

    # 1. Get email from query params or body (based on your API)    
    if event.get('queryStringParameters'):
        email = event['queryStringParameters'].get('email')
    # 2. Extract email from Authorization header    
    else:
       email, error = get_email_from_event(event)
       print(f"email id : {email}")

       if error:
          return error    
        
    

    if not email:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Email is required"})
        }

    # 2. Check email in DynamoDB
    response = dynamodb.get_item(
        TableName=TABLE_NAME,
        Key={
            'email': {'S': email}
        }
    )

    exists = 'Item' in response

    return {
        "statusCode": 200,
        "body": json.dumps({"is_admin": exists})
    }
