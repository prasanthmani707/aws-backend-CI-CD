import boto3

# Initialize SES client
ses = boto3.client('ses', region_name='us-east-1')

def send_wallet_credit_email(email_id, Credits):
    # Extract username from email
    user_name = email_id.split('@')[0].replace('.', ' ').title()  # e.g., john.doe -> John Doe

    try:
        response = ses.send_email(
            Source="eng-team@softmania.in",
            Destination={
                'ToAddresses': [email_id]
            },
            Message={
                'Subject': {
                    'Data': 'SoftMania SplunkLab Wallet Credit Added',
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': f"""Hi {user_name},

We are pleased to inform you that your wallet has been credited successfully.
credits Added: {Credits}

You can now use this credit in your SplunkLab environment.
If you have any questions or need assistance, please contact labsupport@softmania.in.

Thank you,
SoftMania Team
""",
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")


