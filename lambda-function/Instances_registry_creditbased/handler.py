import json
import boto3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from botocore.exceptions import ClientError

ec2_client =boto3.client('ec2')
dynamo =boto3.resource('dynamodb')
TABLE_NAME ="instance_registry_creditbased"
table = dynamo.Table(TABLE_NAME)
updated_time = datetime.utcnow().isoformat()


def get_tag_value(tags, key_name):
     for tag in tags:
         if tag['Key'] == key_name:
             return tag['Value']
     return None

def get_volume_total(volume_ids):
    total_storage =0
    if not volume_ids:
        return 0
    try:
        volumes_response = ec2_client.describe_volumes(VolumeIds=volume_ids)
        print(volumes_response)
        return sum(volume['Size'] for volume in volumes_response['Volumes'])
    except Exception as e:
        print(f"Error fetching volume details: {e}")
        return total_storage

def put_dynamodb_item(instance_id, instance_data, region, terminate_time, total_storage):
    """Insert or overwrite instance data in DynamoDB"""
    try:
        tags = instance_data.get('Tags', [])
        email_id = get_tag_value(tags, 'UserEmail')
        start_time = get_tag_value(tags, 'PlanStartDate')
        instance_name = get_tag_value(tags, 'Name')
        
        item = {
            'instance_id': instance_id,
            'email_id': email_id,
            'start_time': start_time,
            'state': instance_data['State']['Name'],
            'instance_name': instance_name,
            'instance_type': instance_data['InstanceType'],
            'total_storage': total_storage,
            'terminate_time': terminate_time,
            'region': region,
            'timestamp': updated_time
        }
        
        table.put_item(Item=item)
        return True, "Item inserted into DynamoDB"
        
    except Exception as e:
        return False, f"DynamoDB insert failed: {str(e)}"

def get_instance_details(instance_id):  
    try:
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        instance_data = response['Reservations'][0]['Instances'][0]
        return instance_data  
    except ClientError as e: 
        error_code = e.response['Error']['Code']
        if error_code == 'InvalidInstanceID.NotFound':
            print(f"Instance {instance_id} not found")
        else:
            print(f"EC2 describe failed: {error_code} - {str(e)}")
        return None

def updated_termination_state(instance_id, state, terminate_time=None):

     actions = []
     try:
         existing_item = table.get_item(Key={'instance_id': instance_id})

         if 'Item' in existing_item:
             update_expr = "SET #st = :s"
             expr_attr_names = {'#st': 'state'}
             expr_attr_values = {':s': state}

             if state.lower() == 'terminated' and terminate_time:
                 update_expr += ", terminate_time = :term"
                 expr_attr_values[':term'] = terminate_time

             table.update_item(
                 Key = {'instance_id':instance_id},
                 UpdateExpression=update_expr,
                 ExpressionAttributeNames=expr_attr_names,
                 ExpressionAttributeValues=expr_attr_values
             )

             actions.append(f"State updated to {state}")   
         else:
             actions.append("Instance not found for update")

     except Exception as e:
         actions.append(f"Update error: {str(e)}")
     return actions

def handle_termination_event(instance_id, state, terminate_time, actions):
    """Handle terminated state - update state only"""
    actions.extend(updated_termination_state(instance_id, state, terminate_time))
    actions.append("Termination event: storage not updated")
    return {
        'instance_id': instance_id,
        'state': state,
        'terminate_time': terminate_time,
        'actions': actions
    }
def update_stopped_state(instance_id, state):
    actions = []
    try:
        print("Updating stopped state for:", instance_id)

        existing_item = table.get_item(Key={'instance_id': instance_id})
        print("DynamoDB get_item response:", existing_item)

        if not existing_item.get('Item'):
            actions.append("Item not found, inserting new record")

            response = table.put_item(Item={
                'instance_id': instance_id,
                'state': state,
                'timestamp': datetime.utcnow().isoformat()
            })
            print("PutItem response:", response)

        else:
            response = table.update_item(
                Key={'instance_id': instance_id},
                UpdateExpression="SET #st = :state, #ts = :ts",
                ExpressionAttributeNames={
                    '#st': 'state',
                    '#ts': 'timestamp'
                },
                ExpressionAttributeValues={
                    ':state': state,
                    ':ts': datetime.utcnow().isoformat()
                }
            )
            print("UpdateItem response:", response)

            actions.append(f"Stopped state updated: {state}")

        return True, actions

    except Exception as e:
        print("ERROR:", str(e))
        actions.append(f"Stopped state update failed: {str(e)}")
        return False, actions

def handle_stopped_event(instance_id, state, actions):
    """Handle stopped state - update state + timestamp only"""
    success, stop_actions = update_stopped_state(instance_id, state)
    actions.extend(stop_actions)
    actions.append("Stop event: storage not updated")
    return {
        'instance_id': instance_id,
        'state': state,
        'actions': actions
    }

def lambda_handler(event, context): 
     print("EventBridge Event:", event) 
     instance_id = event['detail']['instance-id']
     state = event['detail']['state'] 
     print(f"{state}")
     region = event['region'] 
     actions = [] 

     terminate_time = event.get('time') if state.lower() == 'terminated' else None

     if state.lower() == 'terminated':
         return handle_termination_event(instance_id, state, terminate_time, actions)
    
     if state.lower() == 'stopped':
         return handle_stopped_event(instance_id, state, actions)


     try:
         instance_data = get_instance_details(instance_id)
         if not instance_data:
             actions.append("Failed to get instance details")
         else:
             instance_type = instance_data['InstanceType']
             state = instance_data['State']['Name']

             volume_ids = [
                bd['Ebs']['VolumeId']
                for bd in instance_data.get('BlockDeviceMappings',[])
                if 'Ebs' in bd
             ]

             total_storage = get_volume_total(volume_ids)

             success, message = put_dynamodb_item(instance_id, instance_data, region, terminate_time, total_storage)
             actions.append(message)
     except ClientError as e:
        actions.append(f"Describe instance failed: {str(e)}")

     return {
        'instance_id': instance_id,
        'state': state,
        'terminate_time': terminate_time,
        'actions': actions
     }
