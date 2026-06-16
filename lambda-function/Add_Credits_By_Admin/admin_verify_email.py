import boto3

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Admin')

ses = boto3.client('ses', region_name='us-east-1')
sender_email = "eng-team@softmania.in"


def admin_verify_email(email_id, Credits, admin_email, existing_credits,reason):

    try:

        response = table.scan()
        items = response.get('Items', [])

        email_list = [item['email'] for item in items if 'email' in item]

        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items = response.get('Items', [])
            email_list.extend([item['email'] for item in items if 'email' in item])

        subject = "Admin Support"

        body_text = f"""
Hi Admin,

This is to inform you that an admin has added credit to a user credit account.
reason / Feedback:

{reason}

Transaction Details:
----------------------------------------
Admin Email : {admin_email}
User Email  : {email_id}
Credits      : {Credits}
Previous credits :{existing_credits} 

----------------------------------------

Admin {admin_email} has added {Credits} credit account of user {email_id}.

This notification is sent to all admins for information and transparency.

Regards,
SoftMania
"""

        for email in email_list:

            print("Sending email to:", email)

            ses.send_email(
                Source=sender_email,
                Destination={'ToAddresses': [email]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {'Text': {'Data': body_text}}
                }
            )

        print("✅ Email sent to admins")

    except Exception as e:
        print("❌ Email Error:", str(e))