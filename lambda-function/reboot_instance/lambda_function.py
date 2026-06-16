import boto3
import json
from auth_utils import get_email_from_event

def lambda_handler(event, context):
    print("📩 Incoming event:", json.dumps(event))

    try:
        if 'body' not in event or not event['body']:
            raise ValueError("Missing body in request")

        body = json.loads(event['body'])
        instance_id = body.get('instance_id')  # Can be string or list
        region = body.get('region')

        if not instance_id:
            raise ValueError("Missing instance_id")
        if not region:
            raise ValueError("Missing region")

        # # 🔐 Extract email from Authorization header
        # headers = event.get('headers', {})
        # auth_header = headers.get('authorization') or headers.get('Authorization')
        # email = None
        # if auth_header and auth_header.startswith("Bearer "):
        #     email = auth_header.split("Bearer ")[1].strip()

        # if not email:
        #     raise ValueError("Missing email in headers")


        email, error = get_email_from_event(event)
        print(f"email id : {email}")

        if error:
            return error

        # ✅ Convert string to list OR use list as-is
        if isinstance(instance_id, str):
            instance_ids = [i.strip() for i in instance_id.split(",") if i.strip()]
        else:
            instance_ids = instance_id

        print(f"🔄 Attempting to reboot instances: {instance_ids} in region {region} by {email}")

        ec2 = boto3.client('ec2', region_name=region)
        ec2.reboot_instances(InstanceIds=instance_ids)

        print(f"✅ Reboot command sent for: {instance_ids}")

        return {
            'statusCode': 200,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            },
            'body': json.dumps({"message": f"Instances {instance_ids} in region {region} rebooted by {email}."})
        }

    except Exception as e:
        print("❌ Reboot Error:", str(e))
        return {
            'statusCode': 500,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            },
            'body': json.dumps({"message": "Internal Server Error", "error": str(e)})
        }
