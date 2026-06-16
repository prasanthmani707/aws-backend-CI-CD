import json
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta
from collections import defaultdict
from auth_utils import get_email_from_event

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('User_environment_history_creditbased')

def lambda_handler(event, context):
    try:
        email_id, error = get_email_from_event(event)
        print(f"email id : {email_id}")

        if error:
            return erro

        email_id = email_id.lower()
        print("Email ID:", email_id)

        response = table.query(
            KeyConditionExpression=Key('email_id').eq(email_id),
            ScanIndexForward=True
        )

        items = response.get('Items', [])
        print("Total Items Retrieved:", len(items))

        in_progress_envs = defaultdict(list)
        success_envs = defaultdict(list)
        failed_envs = defaultdict(list)

        in_progress_count = 0
        success_count = 0
        failed_count = 0

        two_days_ago = datetime.utcnow() - timedelta(days=1)
        print("Filtering records created after:", two_days_ago)

        for item in items:

            status = item.get('status', '').lower()
            created_at = item.get('created_at')

            print("Processing Item Status:", status, "Created At:", created_at)

            if not created_at:
                print("Skipping item because created_at is missing")
                continue

            try:
                created_time = datetime.fromisoformat(created_at.replace("Z", ""))
            except Exception as e:
                print("Date parse error:", e)
                continue

            if created_time < two_days_ago:
                print("Skipping item older than 2 days")
                continue

            course_id = item.get('course_id', 'Unknown')

            cleaned_instances = [
                {
                    "instance_id": inst.get("instance_id"),
                    "ServiceType": inst.get("ServiceType"),
                    "Name": inst.get("Name")
                }
                for inst in item.get("instance_ids", [])
            ]

            env_data = {
                "created_at": created_at,
                "environment_name": item.get("environment_name"),
                "instance_ids": cleaned_instances,
                "lab_category": item.get("lab_category"),
                "labs_type": item.get("labs_type"),
                "status": status
            }

            if status == "in_progress":
                in_progress_envs[course_id].append(env_data)
                in_progress_count += 1
                print("Added to IN_PROGRESS:", course_id)

            elif status == "succeeded":
                success_envs[course_id].append(env_data)
                success_count += 1
                print("Added to SUCCEEDED:", course_id)

            elif status == "failed":
                failed_envs[course_id].append(env_data)
                failed_count += 1
                print("Added to FAILED:", course_id)

        result = {
            "email_id": email_id,
            "in_progress_count": in_progress_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "in_progress_environments": dict(in_progress_envs),
            "success_environments": dict(success_envs),
            "failed_environments": dict(failed_envs)
        }

        print("Final Output:", json.dumps(result, indent=2))

        return {
            'statusCode': 200,
            'headers': {
                "Content-Type": "application/json"
            },
            'body': json.dumps(result)
        }

    except Exception as e:
        print("ERROR:", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }