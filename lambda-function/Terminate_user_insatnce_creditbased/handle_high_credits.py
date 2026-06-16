import boto3

scheduler = boto3.client('scheduler')

def handle_high_credits(email):
    safe_email = email.replace("@", "-").replace(".", "-")
    schedule_name = f"terminate-{safe_email}"

    try:
        # 👉 First check if schedule exists
        scheduler.get_schedule(Name=schedule_name)

        # 👉 If no exception → schedule exists → delete it
        scheduler.delete_schedule(Name=schedule_name)
        print(f"✅ Schedule deleted for user: {email}")

    except scheduler.exceptions.ResourceNotFoundException:
        # 👉 Schedule does not exist
        print(f"ℹ️ No schedule found for user: {email}")

    except Exception as e:
        print(f"❌ Error processing schedule for {email}: {str(e)}")