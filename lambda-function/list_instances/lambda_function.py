import boto3
import json
from concurrent.futures import ThreadPoolExecutor
from boto3.dynamodb.conditions import Key
from auth_utils import get_email_from_event

# DynamoDB setup
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('instance_tracker_creditbased')
registry_table = dynamodb.Table('instance_registry_creditbased')


def query_all_pages(dynamodb_table, query_kwargs):
    items = []
    query_kwargs = dict(query_kwargs)

    response = dynamodb_table.query(**query_kwargs)
    items.extend(response.get('Items', []))

    while 'LastEvaluatedKey' in response:
        query_kwargs["ExclusiveStartKey"] = response['LastEvaluatedKey']
        response = dynamodb_table.query(**query_kwargs)
        items.extend(response.get('Items', []))

    return items


# ✅ Fetch all DynamoDB items ONCE (optimized)
def get_all_items(email, instance_ids=None):
    items = []

    if instance_ids is None:
        return query_all_pages(table, {
            "KeyConditionExpression": Key('email_id').eq(email),
            "ProjectionExpression": "instance_id, total_credits, used_time"  # ✅ optimization
        })

    if isinstance(instance_ids, str):
        instance_ids = [instance_ids]

    for instance_id in instance_ids:
        if not instance_id:
            continue

        items.extend(query_all_pages(table, {
            "IndexName": "instance_email_index",
            "KeyConditionExpression": Key('instance_id').eq(instance_id) & Key('email_id').eq(email),
            "ProjectionExpression": "instance_id, total_credits, used_time"  # ✅ optimization
        }))

    return items


def get_active_instance_ids(email):
    instance_ids = []
    seen = set()

    for state in ['running', 'stopped']:
        registry_items = query_all_pages(registry_table, {
            "IndexName": "state-email_id-index",
            "KeyConditionExpression": Key('state').eq(state) & Key('email_id').eq(email),
            "ProjectionExpression": "instance_id"
        })

        for item in registry_items:
            instance_id = item.get('instance_id')
            if not instance_id or instance_id in seen:
                continue

            seen.add(instance_id)
            instance_ids.append(instance_id)

    return instance_ids

def get_ssh_user(ec2, image_id):
    if not image_id:
        return 'ec2-user'

    try:
        response = ec2.describe_images(ImageIds=[image_id])
        if not response.get('Images'):
            return 'ec2-user'

        image_name = response['Images'][0].get('Name', '').lower()

        if 'ubuntu' in image_name:
            return 'ubuntu'
        elif 'amzn' in image_name or 'amazon linux' in image_name:
            return 'ec2-user'
        elif 'centos' in image_name:
            return 'centos'
        elif 'debian' in image_name:
            return 'admin'
        elif 'rhel' in image_name:
            return 'ec2-user'
        else:
            return 'ec2-user'

    except Exception:
        return 'ec2-user'
# ✅ Build credits map (same logic)
def build_credits_map(items):
    credits_map = {}

    for item in items:
        instance_id = item.get('instance_id')

        if instance_id not in credits_map:
            credits_map[instance_id] = {
                "Credits": 0.0,
                "time": 0
            }

        credits_map[instance_id]["Credits"] += float(item.get('total_credits', 0))
        print(f" this the credits {credits_map}")
        credits_map[instance_id]["time"] += int(item.get('used_time', 0))

    return credits_map


def lambda_handler(event, context):

    top_regions = ['us-east-1']

    try:
        # Extract email
        # headers = event.get('headers', {})
        # auth = headers.get('Authorization', '') or headers.get('authorization', '')
        # email = auth.replace("Bearer ", "").strip()
        # body = json.loads(event.get('body', '{}'))

        headers = event.get('headers', {})
        role = headers.get('Role', '') or headers.get('role', '')
        # for mother portal admin page to get email
        if role == 'admin' and headers.get('email_id'):
            email = headers.get('email_id')
            print(f"email id : {email}")
        # for splunk lab page to get email 
        else:
            email, error = get_email_from_event(event)
            print(f"email id : {email}")
            if error:
              return error



        # ✅ Get all credits data ONCE
        active_instance_ids = get_active_instance_ids(email)

        if not active_instance_ids:
            return {
                'statusCode': 200,
                'headers': {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS"
                },
                'body': json.dumps([])
            }

        all_items = get_all_items(email, active_instance_ids)
        credits_map = build_credits_map(all_items)

        all_instances = []

        def fetch_region(region):
            local_instances = []
            image_cache = {} 
            def get_cached_ssh_user(ec2, image_id):
                if image_id in image_cache:
                    return image_cache[image_id]

                user = get_ssh_user(ec2, image_id)
                image_cache[image_id] = user
                return user

            try:
                ec2 = boto3.client('ec2', region_name=region)

                paginator = ec2.get_paginator('describe_instances')
                filters = [
                    {'Name': 'tag:Owner', 'Values': [email]},
                    {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}  # ✅ small optimization
                ]
                filters.append({'Name': 'instance-id', 'Values': active_instance_ids})

                pages = paginator.paginate(Filters=filters)

                for page in pages:
                    for reservation in page['Reservations']:
                        for instance in reservation['Instances']:

                            tags = instance.get('Tags', [])
                            tag_dict = {t['Key']: t['Value'] for t in tags}

                            # Skip unwanted product
                            if tag_dict.get('Product') == 'mother-portal':
                                continue

                            instance_id = instance['InstanceId']

                            # Basic details
                            state = instance['State']['Name']
                            private_ip = instance.get('PrivateIpAddress', '')
                            public_ip = instance.get('PublicIpAddress', '')
                            public_dns = instance.get('PublicDnsName', '')
                            key_name = instance.get('KeyName', '')
                            image_id = instance.get('ImageId', '')

                            # Tags (same output)
                            name_tag = tag_dict.get('Name', '')
                            service_type = tag_dict.get('ServiceType', 'Unknown')
                            plan_start_date = tag_dict.get('PlanStartDate', '')
                            category = tag_dict.get('Category', '')
                            course_id = tag_dict.get('CourseID', 'General')

                            # SSH logic (same behavior)
                            ssh_user = get_cached_ssh_user(ec2, image_id)
                            ssh_command = (
                                f'ssh -i "{key_name}.pem" {ssh_user}@{public_dns}'
                                if key_name and public_dns else "-"
                            )

                            # Credits lookup (same output)
                            credits_data = credits_map.get(instance_id, {"Credits": 0, "time": 0})

                            local_instances.append({
                                "InstanceId": instance_id,
                                "Name": name_tag,
                                "RunningTime": credits_data["time"],
                                "Credits": credits_data["Credits"],
                                "State": state,
                                "PrivateIp": private_ip,
                                "PublicIp": public_ip,
                                "PublicDns": public_dns,
                                "KeyName": key_name,
                                "SSHCommand": ssh_command,
                                "Region": region,
                                "ServiceType": service_type,
                                "PlanStartDate": plan_start_date,
                                "Category": category,
                                "CourseID": course_id
                            })

            except Exception as e:
                print(f"Error in region {region}: {str(e)}")

            return local_instances

        with ThreadPoolExecutor(max_workers=3) as executor:
            results = executor.map(fetch_region, top_regions)

        for region_result in results:
            all_instances.extend(region_result)

        return {
            'statusCode': 200,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS"
            },
            'body': json.dumps(all_instances)
        }

    except Exception as e:
        print("Lambda Error:", str(e))
        return {
            'statusCode': 500,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS"
            },
            'body': json.dumps({"message": "Internal Server Error", "error": str(e)})
        }




# if __name__ == "__main__":
#     test_event = {
#         "headers": {
#             "Role": "admin",
#             "email_id": "lenomicheal8@gmail.com"
#         },
#         "queryStringParameters": {
#             # "instance_id": "i-0123456789abcdef0"   # optional
#         },
#         "body": None
#     }

#     result = lambda_handler(test_event, None)
#     print(json.dumps(result, indent=2))
