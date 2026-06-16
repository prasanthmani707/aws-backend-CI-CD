import boto3
from boto3.dynamodb.conditions import Key
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('instance_tracker_creditbased')


def query_by_date(date_str):
    response = table.query(
        IndexName='daily_usage_filter',
        KeyConditionExpression=Key('usage_date').eq(date_str)
    )
    logger.info(f"Fetched {len(response.get('Items', []))} items for {date_str}")
    return response.get('Items', [])