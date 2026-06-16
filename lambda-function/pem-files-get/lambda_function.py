import boto3
import os
import json
from auth_utils import get_email_from_event
s3 = boto3.client("s3")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "splunklab-dev")

def lambda_handler(event, context):
    print("📩 Event received:", event)
    print("📝 Event type:", type(event))  # ✅ Added statement

    try:
        if "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        else:
            body = event
        user_email, error = get_email_from_event(event)
        print(f"email id : {user_email}")

        if error:
            return error
        instance_id = body.get('instance_id')
        print(f"🔍 Checking PEM files for: {user_email}")

        if not user_email:
            print("⚠️ No email provided.")
            return { "statusCode": 400, "body": "Missing email" }

        prefix = f"clients/{user_email}/keys/"
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=prefix)

        pem_files = []
        if "Contents" in response:
            for obj in response["Contents"]:
                key = obj["Key"]
                if key.endswith(".pem"):
                    signed_url = s3.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': BUCKET_NAME, 'Key': key},
                        ExpiresIn=3600
                    )
                    pem_files.append({
                        "filename": key.split("/")[-1],
                        "url": signed_url
                    })
        print(f"✅ Found {len(pem_files)} PEM files for {user_email}")

        # 🔹 Structured log with region + email + count
        print(json.dumps({
            "action": "pem_lookup",
            "region": os.environ.get("AWS_REGION", "unknown"),
            "email": user_email,
            "instance_id": instance_id,
            "found_files": len(pem_files),
            "files": [f["filename"] for f in pem_files]
        }))
    
        return {
            "statusCode": 200,
            "body": json.dumps({ "files": pem_files })
        }

    except Exception as e:
        print("❌ Exception occurred:", str(e))
        return {
            "statusCode": 500,
            "body": f"Error: {str(e)}"
        }
