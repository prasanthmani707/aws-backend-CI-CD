import json
import boto3

ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    email_id = event.get("email")
    
    if not email_id:
        return {
            "statusCode": 400,
            "body": "Email not provided in event"
        }

    print(f"Looking for instances with tag Email={email_id}")

    try:
        response = ec2.describe_instances(
            Filters=[
                {
                    'Name': 'tag:UserEmail',
                    'Values': [email_id]
                },
                {
                    'Name': 'instance-state-name',
                    'Values': ['pending', 'running', 'stopping', 'stopped']    
                }
            ]
        )

        instance_ids = [
            instance['InstanceId']
            for reservation in response['Reservations']
            for instance in reservation['Instances']
        ]

        if instance_ids:
            ec2.terminate_instances(InstanceIds=instance_ids)
            print("Terminated:", instance_ids)

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Instances terminated",
                    "instances": instance_ids
                })
            }
        else:
            print("No instances found")

            return {
                "statusCode": 200,
                "body": json.dumps("No instances found")
            }

    except Exception as e:
        print("Error:", str(e))

        return {
            "statusCode": 500,
            "body": json.dumps(str(e))
        }
    