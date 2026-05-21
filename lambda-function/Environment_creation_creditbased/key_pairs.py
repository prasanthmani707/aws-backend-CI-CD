import boto3
import re
from botocore.exceptions import ClientError

# AWS clients
ec2 = boto3.client("ec2")
s3 = boto3.client("s3")

BUCKET = "splunklab-dev"
def check_ec2_key_exists(key_name):
    try:
        ec2.describe_key_pairs(KeyNames=[key_name])
        return True
    except:
        return False

def check_s3_key_exists(usermail, key_name):
    try:
        key_path = f"clients/{usermail}/keys/{key_name}.pem"
        s3.head_object(Bucket=BUCKET, Key=key_path)
        return True
    except:
        return False

def create_ec2_key_and_upload(usermail, base_name):
    clean_name = re.sub(r'[^a-zA-Z0-9\-]', '-', base_name)
    final_name = clean_name
    suffix = 1

    # 🟡 Check if any PEM key already exists for this user (username.pem or username-1.pem)
    existing_keys = s3.list_objects_v2(
        Bucket=BUCKET,
        Prefix=f"clients/{usermail}/keys/{clean_name}"
    )

    if 'Contents' in existing_keys and existing_keys['KeyCount'] > 0:
        print(f"🔐 Existing PEM key already found in S3 for {usermail}. Skipping new key creation.")
        return clean_name

    while check_ec2_key_exists(final_name) or check_s3_key_exists(usermail, final_name):
        final_name = f"{clean_name}-{suffix}"
        suffix += 1

        if check_s3_key_exists(usermail, final_name):
            print(f"🔐 Key already exists in S3 for user {usermail}: {final_name}. Skipping creation.")
            return final_name

    try:
        response = ec2.create_key_pair(KeyName=final_name)
        private_key = response['KeyMaterial']
        key_path = f"clients/{usermail}/keys/{final_name}.pem"
        s3.put_object(Bucket=BUCKET, Key=key_path, Body=private_key.encode(), ACL='private')
        print(f"✅ Created EC2 KeyPair and uploaded to S3: {key_path}")
    except Exception as e:
        print(f"❌ Failed to create EC2 key pair: {str(e)}")
        raise e

    return final_name
