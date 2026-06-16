import json
import boto3
from decimal import Decimal
from auth_utils import get_email_from_event

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Users_Credits_Creditbased')

def lambda_handler(event, context):
    email_id, error = get_email_from_event(event)
    print(f"email id : {email_id}")

    if error:
        return error
    try:
        response = table.get_item(
            Key={'email_id': email_id}
        )

        if 'Item' in response:
            Current_Credits = response['Item'].get('current_credits', 0)
            expire_at = response['Item'].get('expire_at',"")
            # Convert Decimal to float
            if isinstance(Current_Credits, Decimal):
                Current_Credits = float(Current_Credits)

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'current_credits': Current_Credits,
                    'expire_at':expire_at

                })
            }
        else:
            return {
                'statusCode': 404,
                'body': json.dumps('Email ID does not exist')
            }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }
