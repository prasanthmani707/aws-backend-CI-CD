import boto3

sender_email = "eng-team@softmania.in"

# Initialize SES client
ses = boto3.client('ses', region_name='us-east-1')


def send_welcome_email(email_id, Credits):
    
    # Extract username from email
    user_name = email_id.split('@')[0].replace('.', ' ').title()

    try:
        response = ses.send_email(
            Source=sender_email,
            Destination={
                'ToAddresses': [email_id]
            },
            Message={
                'Subject': {
                    'Data': f'Welcome to SoftMania SplunkLab',
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': f"""Hi {user_name},


New credits have been added to your SoftMania SplunkLab account, and they are now available for use.
Account Email: {email_id}
Available Credits: {Credits}

Our platform operates on a credit-based system. Credits are consumed based on your usage, including
• Compute credits
• Storage credits

You can now create and manage your environment using the platform below:
https://splunklab.softmania.in/

You'll receive automated alerts based on usage. Stay informed and plan accordingly.
If you experience any issues or need assistance, please contact our support team.
Support: labsupport@softmania.in
We’re excited to have you onboard!

Best regards,
Softmania Team
""",
                        'Charset': 'UTF-8'
                    }
                }
            }
        )

        print("Welcome email sent successfully")

    except Exception as e:
        print(f"Failed to send email: {e}")