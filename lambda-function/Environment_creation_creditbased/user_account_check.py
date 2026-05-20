import json
import re 
import boto3
import random
import datetime

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Users_Credits_Creditbased')

def user_account_check(usermail):
    response = table.get_item(
        Key={"email_id": usermail}
    )

    # If user not found
    if "Item" not in response:
        return False

    balance = response["Item"]["current_credits"]

    # Invalid if balance is exactly 10
    if balance <= 10:
        return False

    return True
