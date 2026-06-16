import boto3
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
pricing_catalog = dynamodb.Table("Credits_Rate_Creditbased")

def get_backend_credits():
    resource_type = "ec2#sa-east-1#t3.medium"
    response = pricing_catalog.get_item(Key={"resource_type": resource_type})
    item = response.get("Item")
    if not item:
        return None
    return Decimal(str(item["platform_credits"]))