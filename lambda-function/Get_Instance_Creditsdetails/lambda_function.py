import json
import boto3
from decimal import Decimal
from datetime import datetime
from boto3.dynamodb.conditions import Key
# from auth_utils import get_email_from_event

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Credits_Rate_Creditbased')

def lambda_handler(event, context):
    # email_id, error = get_email_from_event(event)
    # print(f"email id : {email_id}")

    # if error:
    #     return error

    body = json.loads(event['body'])
    instance_type = body['instance_type']

    resource_type = f"ec2#sa-east-1#{instance_type}"
    ebs_resource_type = "EBS#sa-east-1#gp3"

    response1 = table.query(
        KeyConditionExpression=Key('resource_type').eq(resource_type)
    )

    response2 = table.query(
        KeyConditionExpression=Key('resource_type').eq(ebs_resource_type)
    )

    ins_type_credits_per_hour = None
    ebs_credits_per_hour = None

    if response1['Items']:
        ins_type_credits_per_hour = response1['Items'][0]['credits_per_hour']
        platform_credits = response1['Items'][0]['platform_credits']

    if response2['Items']:
        ebs_credits_per_hour = response2['Items'][0]['credits_per_hour']

    return {
        'statusCode': 200,
        'body': json.dumps({
            'instance_type': instance_type,
            'ins_type_credits_per_hour': ins_type_credits_per_hour,
            'platform_credits': platform_credits,
            'EBS_credits_per_hour': ebs_credits_per_hour
        })
    }