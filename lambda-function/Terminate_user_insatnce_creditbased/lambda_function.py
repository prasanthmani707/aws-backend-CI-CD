import boto3
import math
from datetime import datetime, timedelta
from boto3.dynamodb.conditions import Key
from fetch_instance_by_email import fetch_instance_by_email
from fetch_instance_by_email import remove_expiry_from_db
from calculate_expiry import calculate_expiry
from create_termination_schedule import create_termination_schedule
from handle_high_credits import handle_high_credits


dynamodb = boto3.resource('dynamodb')
instance_table = dynamodb.Table('instance_registry_creditbased')

maximum = 500 

def lambda_handler(event, context):
    try:
        for record in event.get('Records', []):
            if record.get('eventName') not in ['INSERT', 'MODIFY']:
                continue

            new_image = record['dynamodb']['NewImage']

            email = new_image['email_id']['S']
            current_credits = float(new_image['current_credits']['N'])

            print(f"\nUser: {email}")
            print(f"Credits: {current_credits}")

            # 👉 Only run storage logic if credits <= 500
            if current_credits > maximum:
                handle_high_credits(email)
                remove_expiry_from_db(email)
                continue

            # 🔥 Fetch stopped instances
            stopped_instances = fetch_instance_by_email(email)

            print("Total instances fetched:", len(stopped_instances))

            if not stopped_instances:
                print("No stopped instances")
                handle_high_credits(email)
                remove_expiry_from_db(email)
                continue

            # 🔥 Calculation
            result = calculate_expiry(stopped_instances, current_credits)

            if not result:
                print("No valid calculation")
                continue
            schedule_name = create_termination_schedule(email,result,current_credits,)

            

        return {
            "status": "success"
        }

    except Exception as e:
        print("Error:", str(e))
        return {
            "status": "error",
            "message": str(e)
        }