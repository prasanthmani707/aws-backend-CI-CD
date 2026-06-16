import boto3
from decimal import Decimal

# DynamoDB setup
dynamodb = boto3.resource('dynamodb')
credits_table = dynamodb.Table('Users_Credits_Creditbased')

def check_user_exists(email_id):
    """
    Checks if a user exists and returns a tuple:
    (exists: bool, current_credits: Decimal or 0)
    """
    response = credits_table.get_item(
        Key={'email_id': email_id},
        ProjectionExpression='email_id, current_credits'
    )
    
    if 'Item' in response:
        current_credits = response['Item'].get('current_credits', Decimal('0'))
        return True, current_credits
    else:
        return False, Decimal('0')