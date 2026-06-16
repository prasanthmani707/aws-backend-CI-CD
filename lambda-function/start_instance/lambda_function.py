import json
import boto3
from decimal import Decimal
from auth_utils import get_email_from_event

# -----------------------------
# Global clients (reuse = faster)
# -----------------------------
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Users_Credits_Creditbased')

ec2_clients = {}

LIMIT = 5


def get_ec2_client(region):
    """Reuse EC2 client per region to reduce cold creation overhead"""
    if region not in ec2_clients:
        ec2_clients[region] = boto3.client('ec2', region_name=region)
    return ec2_clients[region]


def lambda_handler(event, context):
    try:
        # -----------------------------
        # Parse request body
        # -----------------------------
        body = json.loads(event.get('body') or "{}")

        instance_id = body.get('instance_id')
        region = body.get('region')

        if not instance_id:
            return error(400, "Missing instance_id in body")
        if not region:
            return error(400, "Missing region in body")

        # -----------------------------
        # Extract email from headers
        # -----------------------------
        # headers = event.get('headers', {})
        # auth_header = headers.get('authorization') or headers.get('Authorization')

        # if not auth_header or not auth_header.startswith("Bearer "):
        #     return error(401, "Missing or invalid Authorization header")

        # email = auth_header.split("Bearer ")[1].strip()

        email, error = get_email_from_event(event)
        print(f"email id : {email}")

        if error:
            return error

        # -----------------------------
        # Normalize instance IDs
        # -----------------------------
        if isinstance(instance_id, str):
            instance_ids = [i.strip() for i in instance_id.split(",") if i.strip()]
        elif isinstance(instance_id, list):
            instance_ids = instance_id
        else:
            return error(400, "instance_id must be string or list")

        if not instance_ids:
            return error(400, "No valid instance IDs provided")

        # -----------------------------
        # Fetch credits balance (FAST get_item instead of query)
        # -----------------------------
        response = table.get_item(Key={'email_id': email})
        item = response.get('Item')

        if not item:
            return error(404, f"User {email} not found in CREDIT_ACCOUNT")

        current_credits = item.get('current_credits', 0)

        # Convert safely
        if isinstance(current_credits, Decimal):
            current_credits = float(current_credits)
        else:
            current_credits = float(current_credits)

        # -----------------------------
        # credits check
        # -----------------------------
        if current_credits <= LIMIT:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    "message": "CREDITS Required: Insufficient credits."
                })
            }

        # -----------------------------
        # Start EC2 instances
        # -----------------------------
        ec2 = get_ec2_client(region)

        print(f"Starting instances={instance_ids}, region={region}, user={email}")

        ec2.start_instances(InstanceIds=instance_ids)

        # -----------------------------
        # Success response
        # -----------------------------
        return {
            'statusCode': 200,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            },
            'body': json.dumps({
                "message": f"Instances started successfully",
                "instance_ids": instance_ids,
                "region": region,
                "current_credits": current_credits
            })
        }

    except Exception as e:
        print("ERROR:", str(e))
        return error(500, "Internal Server Error", str(e))


def error(code, message, detail=None):
    """Standard error response helper"""
    body = {"message": message}
    if detail:
        body["error"] = detail

    return {
        'statusCode': code,
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*"
        },
        'body': json.dumps(body)
    }