import boto3
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table("Credits_Rate_Creditbased")
resource_type = "EBS#sa-east-1#gp3"
def fetch_per_hour_gp_credits():
    response = table.get_item(
        Key ={
            'resource_type':resource_type
        }
    )
    item = response.get("Item")

    if item:
        return item.get("credits_per_hour")
    else:
        return None

