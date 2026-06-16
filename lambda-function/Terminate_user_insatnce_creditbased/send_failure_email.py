import boto3
import json
import os
from datetime import datetime, timezone, timedelta

ses = boto3.client('ses')

# 🔥 Replace with your verified emails
ADMIN_EMAIL = "prasanth.mani@softmania.in"
SENDER_EMAIL = "labsupport@softmania.in"
def send_failure_email(email, error_message):
    try:
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={
                "ToAddresses": [ADMIN_EMAIL]
            },
            Message={
                "Subject": {
                    "Data": f"[ALERT] Schedule Creation Failed for {email}"
                },
                "Body": {
                    "Text": {
                        "Data": f"""
Failed to create termination schedule.

User: {email}
Error: {error_message}
"""
                    }
                }
            }
        )
        print("✅ Failure email sent")

    except Exception as e:
        print("❌ Error sending SES email:", str(e))

def alert_email(email,expiry_date,formatted_days_remaining):
    html_body = load_html_template(email,expiry_date,formatted_days_remaining)
    try:
        ses.send_email(
            Source=SENDER_EMAIL,
            Destination={
                "ToAddresses": [email]
            },
            Message={
                "Subject": {
                    "Data": f" Schedule ALERT from Softmania"
                },
                "Body": {
                    "Html": {
                        "Data":html_body
                    }
                }
            }
        )
        print("✅ user email sent")

    except Exception as e:
        print("❌ Error sending SES email:", str(e))

def load_html_template(email, expiry_date, formatted_days_remaining):
    IST = timezone(timedelta(hours=5, minutes=30))
    expiry_ist = expiry_date.astimezone(IST)
    formatted_expiry = expiry_ist.strftime('%d %b %Y, %I:%M %p (IST)')
    
    print(os.listdir('/var/task'))
    print(os.listdir('/var/task/templates'))
    template_path = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "alert_email.html"
    )

    with open(template_path, "r", encoding="utf-8") as file:
        html = file.read()

    html = html.replace("{{email}}", email)
    html = html.replace("{{expiry_date}}", str(formatted_expiry))
    html = html.replace("{{formatted_days_remaining}}", str(formatted_days_remaining))

    return html
