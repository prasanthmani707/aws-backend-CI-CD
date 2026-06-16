import boto3
import json
from auth_utils import get_email_from_event

def lambda_handler(event, context):
    try:
        print(f"📩 Received event: {json.dumps(event)}")

        if 'body' not in event or not event['body']:
            raise ValueError("Missing body in request")

        body = json.loads(event['body'])

        instance_id = body.get('instance_id')  # Can be string or list
        region = body.get('region')

        #🔐 Extract email from Authorization header
        # headers = event.get('headers', {})
        # auth_header = headers.get('authorization') or headers.get('Authorization')
        # email = None
        # if auth_header and auth_header.startswith("Bearer "):
        #     email = auth_header.split("Bearer ")[1].strip()

        email, error = get_email_from_event(event)
        print(f"email id : {email}")

        if error:
            return error

        if not instance_id:
            raise ValueError("Missing instance_id")
        if not region:
            raise ValueError("Missing region")
        if not email:
            raise ValueError("Missing email in headers")

        # ✅ Convert comma string to list OR keep list as-is
        if isinstance(instance_id, str):
            instance_list = [i.strip() for i in instance_id.split(",") if i.strip()]
        else:
            instance_list = instance_id

        print(f"🛑 Stopping instances: {instance_list} in region {region} by {email}")

        ec2 = boto3.client('ec2', region_name=region)
        response = ec2.stop_instances(InstanceIds=instance_list)

        print(f"🔄 Stop response: {response}")

        return {
            'statusCode': 200,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            },
            'body': json.dumps({
                "message": f"Instances {instance_list} in region {region} stopped by {email}."
            })
        }

    except Exception as e:
        print("❌ Stop Error:", str(e))
        return {
            'statusCode': 500,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            },
            'body': json.dumps({
                "message": "Internal Server Error",
                "error": str(e)
            })
        }
