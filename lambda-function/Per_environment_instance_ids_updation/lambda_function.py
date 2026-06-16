import json
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("User_environment_history_creditbased")
ec2 = boto3.client('ec2') 

def lambda_handler(event, context):

    email = event.get("email")
    build_id = event.get("build_id")
    instance_id = event.get("instance_id")  
    print(f"buildID {build_id}") # 🆕 new instance

    # ✅ Validation
    if not email or not email.strip():
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "Missing required field: email"
            })
        }

    response = ec2.describe_instances(InstanceIds=[instance_id])
    tags = response['Reservations'][0]['Instances'][0].get('Tags', [])

    name_tag = next((tag['Value'] for tag in tags if tag['Key'] == 'Name'), None)
    ServiceType = next((tag['Value'] for tag in tags if tag['Key'] == 'ServiceType'), None)
    CourseID = next((tag['Value'] for tag in tags if tag['Key'] == 'CourseID'), None)


    if not build_id or not instance_id:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "build_id and instance_id are required"
            })
        }

    # ✅ Update WITHOUT overwriting (append)
    table.update_item(
        Key={
            "email_id": email,
            "build_id": build_id
        },
        UpdateExpression="""
            SET instance_ids = list_append(
                if_not_exists(instance_ids, :empty_list),
                :new_instance

            )
        """,
        ExpressionAttributeValues={
            ":new_instance": [{
                "instance_id": instance_id,
                "Name":name_tag,
                "ServiceType": ServiceType,
                "CourseID":CourseID,
            }],   # must be a list
            ":empty_list": []
        }
    )

    return {
        "statusCode": 200,
        "body": json.dumps("Instance ID added successfully")
    }