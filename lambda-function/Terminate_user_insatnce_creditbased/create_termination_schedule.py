import boto3
import json
from datetime import datetime, timedelta
from send_failure_email import send_failure_email ,alert_email
from fetch_instance_by_email import update_expiry_in_db
from datetime import timezone

scheduler = boto3.client('scheduler')

LAMBDA_ARN = "arn:aws:lambda:us-east-1:813348525611:function:user_instance_terminate_by_schedule_creditbased"
ROLE_ARN = "arn:aws:iam::813348525611:role/eventbridge_instance_schudule_role-DEV"


def create_termination_schedule(email, result,current_credits):
    expiry_date=result.get("expiry_date")
    formatted_days_remaining =result.get("formatted_days_remaining")

    try:
        safe_email = email.replace("@", "-").replace(".", "-")
        schedule_name = f"terminate-{safe_email}"

        # ✅ Normalize expiry time to fixed time (01:00 AM)

        new_time_str = expiry_date.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
        new_expression = f"at({new_time_str})"

        try:
            # 🔍 Get existing schedule
            response = scheduler.get_schedule(Name=schedule_name,GroupName="default")

            existing_expression = response.get("ScheduleExpression", "")
            existing_time_str = existing_expression.replace("at(", "").replace(")", "")

            print(f"Existing schedule time: {existing_time_str}")
            print(f"New schedule time: {new_time_str}")

            # ✅ Compare only normalized values
            if existing_time_str == new_time_str:
                print(f"✅ Schedule already up-to-date: {schedule_name}")
                update_expiry_in_db(email, expiry_date)
                return schedule_name

            print("🔄 Updating schedule...")

            scheduler.update_schedule(
                Name=schedule_name,
                GroupName="default",
                ScheduleExpression=new_expression,
                ScheduleExpressionTimezone="UTC",
                FlexibleTimeWindow={"Mode": "OFF"},
                Target={
                    "Arn": LAMBDA_ARN,
                    "RoleArn": ROLE_ARN,
                    "Input": json.dumps({"email": email})
                }
            )
            

            print(f"✅ Schedule updated: {schedule_name}")
            update_expiry_in_db(email, expiry_date)
            return schedule_name

        except scheduler.exceptions.ResourceNotFoundException:
            print(f"🆕 Creating new schedule for: {email}")

            scheduler.create_schedule(
                Name=schedule_name,
                GroupName="default",
                ScheduleExpression=new_expression,
                ScheduleExpressionTimezone="UTC",
                FlexibleTimeWindow={"Mode": "OFF"},
                Target={
                    "Arn": LAMBDA_ARN,
                    "RoleArn": ROLE_ARN,
                    "Input": json.dumps({"email": email})
                }
            )

            print(f"✅ Schedule created: {schedule_name}")
            print(f"updating the db {expiry_date}")
            update_expiry_in_db(email, expiry_date)
            alert_email(email,expiry_date,formatted_days_remaining)
            return schedule_name

    except Exception as e:
        error_message = str(e)
        print("❌ Error creating/updating schedule:", error_message)
        send_failure_email(email, error_message)
        return None