import json
import boto3
from boto3.dynamodb.conditions import Key
from server_creation_email_sender import email_notify

dynamodb = boto3.resource("dynamodb")
status_table = dynamodb.Table("User_environment_history_creditbased")

def lambda_handler(event, context):
    try:
        # 1️⃣ Read values from EventBridge (CodeBuild)
        raw_build_id = event["detail"]["build-id"]
        build_status = event["detail"]["build-status"]
        project_name = event["detail"]["project-name"]

        # CodeBuild format: project-name:uuid
        build_uuid = raw_build_id.split("/")[-1]
        build_id = build_uuid

        print("Build ID:", build_id)
        print("Build Status:", build_status)
        print("Project Name:", project_name)

        # 2️⃣ Query DynamoDB using GSI (build_id)
        response = status_table.query(
            IndexName="codebuild_status_fetch",
            KeyConditionExpression=Key("build_id").eq(build_id)
        )

        if response["Count"] == 0:
            print("No record found for build_id:", build_id)
            return {
                "statusCode": 200,
                "body": json.dumps("No matching record found")
            }

        # 3️⃣ Extract PK and SK from result
        item = response["Items"][0]

        email_id = item["email_id"]   # PK
        build_id = item["build_id"]   # SK (same value)

        # 4️⃣ Update item using PRIMARY KEY
        status_table.update_item(
            Key={
                "email_id": email_id,
                "build_id": build_id
            },
            UpdateExpression="SET #st = :status",
            ExpressionAttributeNames={
                "#st": "status"
            },
            ExpressionAttributeValues={
                ":status": build_status
            }
        )
        print("Build status updated successfully")
        email_notify(email_id, build_status,project_name)

        return {
            "statusCode": 200,
            "body": json.dumps("Build status updated successfully")
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps(str(e))
        }