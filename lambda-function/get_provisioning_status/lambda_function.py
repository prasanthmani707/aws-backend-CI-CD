import json
import boto3
from boto3.dynamodb.conditions import Key
from auth_utils import get_email_from_event


dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ProvisioningStatus')

def lambda_handler(event, context):
    # Extract email (from query string or event body)
    # email = None
    # if event.get("queryStringParameters") and event["queryStringParameters"].get("email"):
    #     email = event["queryStringParameters"]["email"]
    # elif event.get("body"):
    #     body = json.loads(event["body"])
    #     email = body.get("email")

    email, error = get_email_from_event(event)
    print(f"email id : {email}")

    if error:
        return error    
    
    if not email:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing 'email' in token"})
        }

    try:
        # Query using Partition Key (email)
        response = table.query(
            KeyConditionExpression=Key('email').eq(email)
        )
        items = response.get('Items', [])

        # Convert DynamoDB types to normal Python types
        def simplify_item(item):
            return {
                "email": item.get("email"),
                "build_id": item.get("build_id"),
                "instance_ids": item.get("instance_ids", []),
                "project": item.get("project", ""),
                "started": item.get("started_at", ""),
                "status": item.get("status", "")
            }

        result = [simplify_item(i) for i in items]

        return {
            "statusCode": 200,
            "body": json.dumps(result),
            "headers": {
                "Content-Type": "application/json"
            }
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
