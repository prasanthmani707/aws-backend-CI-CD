import boto3
import json
from auth_utils import get_email_from_event

def lambda_handler(event, context):
    try:
        print("📦 Raw event:", json.dumps(event))

        if 'body' not in event or not event['body']:
            raise ValueError("Missing body in request")

        body = json.loads(event['body'])
        instance_id = body.get('instance_id') or body.get('instance_ids')  # string or list
        region = body.get('region')

        #Extract email from Authorization header
        # email, error = get_email_from_event(event)
        # print(f"email id : {email}")

        # if error:
        #     return error
        if not instance_id:
            raise ValueError("Missing instance_id in body")
        if not region:
            raise ValueError("Missing region in body")

        # if not email:
        #     raise ValueError("Missing email in headers")

        #  Handle single or multiple IDs
        if isinstance(instance_id, str):
            instance_ids = [i.strip() for i in instance_id.split(",") if i.strip()]
        else:
            instance_ids = instance_id

        # print(f"Terminating  instances: {instance_ids} in region: {region} by {email}")

        ec2 = boto3.client('ec2', region_name=region)
        ec2.terminate_instances(InstanceIds=instance_ids)


        return response(200, {
            "message": "Instance termination initiated",
            "region": region,
            "instance_ids": instance_ids
        })

    except Exception as e:
        return response(500, {"error": str(e)})


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }
