import boto3
from decimal import Decimal

# Initialize SES client
ses = boto3.client('ses', region_name='us-east-1')

def send_credit_email(email_id, Credits, existing_credits):
    """
    Send wallet credit email including previous credits, added Credits, and new credits.
    
    Parameters:
    - email_id: str
    - Credits: Decimal or float
    - existing_credits: Decimal or float
    """
    # Extract username from email
    user_name = email_id.split('@')[0].replace('.', ' ').title()  # e.g., john.doe -> John Doe

    # Calculate new credits
    new_credits = Decimal(existing_credits) + Decimal(Credits)

    # Email body
    email_body = f"""Hi {user_name},

We are pleased to inform you that your wallet has been credited successfully.

Previous credits: {existing_credits}
credits Added: {Credits}
Total credits: {new_credits}

You can now use this credit in your SplunkLab environment.
If you have any questions or need assistance, please contact labsupport@softmania.in.

Thank you,
SoftMania Team
"""

    try:
        response = ses.send_email(
            Source="eng-team@softmania.in",
            Destination={'ToAddresses': [email_id]},
            Message={
                'Subject': {
                    'Data': 'SoftMania SplunkLab  Account Credit Added',
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': email_body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        print("✅ Email sent successfully")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")