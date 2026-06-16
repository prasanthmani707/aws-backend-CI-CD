import boto3
dynamodb = boto3.resource('dynamodb')
wallet_table = dynamodb.Table('Users_Credits_Creditbased')
def check_user_exists(email_id):
    response = wallet_table.get_item(
        Key={'email_id': email_id},
        ProjectionExpression='email_id'
    )
    return 'Item' in response