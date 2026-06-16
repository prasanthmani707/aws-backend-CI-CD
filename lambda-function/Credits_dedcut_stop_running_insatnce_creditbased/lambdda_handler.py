import json
import boto3

ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    messages = []

    for record in event.get("Records", []):
        if record.get("eventName") != "MODIFY":
            continue
        
        new_image = record["dynamodb"].get("NewImage")
        if not new_image:
            messages.append("⏭ No NewImage")
            continue
        
        UserEmail = new_image.get("email_id", {}).get("S")
        current_credits = new_image.get("current_credits", {}).get("N")
        
        if not UserEmail or current_credits is None:
            continue
        
        if float(current_credits) <= 5:
            msg = f"⚠️ Low balance for {UserEmail}: {current_credits}"
            print(msg)
            messages.append(msg)
            
            response = ec2.describe_instances(
                Filters=[
                    {'Name': 'tag:UserEmail', 'Values': [UserEmail]},
                    {'Name': 'instance-state-name', 'Values': ['running', 'pending']}
                ]
            )
            
            instances_to_stop = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instances_to_stop.append(instance['InstanceId'])
                
            if instances_to_stop:
                msg = f"Stopping instances: {instances_to_stop}"
                print(msg)
                messages.append(msg)
                ec2.stop_instances(InstanceIds=instances_to_stop)
            else:
                msg = f"No running instances found for {UserEmail}"
                print(msg)
                messages.append(msg)
    
    return {
        'statusCode': 200,
        'body': json.dumps(messages)
    }