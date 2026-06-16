import boto3
from decimal import Decimal

region = "us-west-2"
dynamodb = boto3.resource('dynamodb', region_name=region)
table = dynamodb.Table('CommunityMembers')

def apply_member_discount(email_id, Credits):
    """
    Returns:
        final_credits (Decimal): credits after discount
        discount_credits (Decimal): discount applied
    """
    response = table.get_item(Key={'email': email_id})
    
    if response.get('Item'):
        # 25% discount
        discount_credits = Credits * Decimal('0.25')
        final_credits = Credits - discount_credits
        print(f"Community member discount applied: ${discount_credits}, final credits: ${final_credits}")
    else:
        final_credits = Credits
        discount_credits = Decimal('0')
        print(f"No discount applied, credits to pay: ${final_credits}")
    
    return final_credits, discount_credits