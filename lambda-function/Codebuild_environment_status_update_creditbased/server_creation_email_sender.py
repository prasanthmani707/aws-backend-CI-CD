import boto3

ses = boto3.client('ses', region_name='us-east-1')

def email_notify(email_id, build_status, project_name):
    if build_status != 'SUCCEEDED':
        print("Build not successful. Email not sent.")
        return

    # Extract username from email
    user_name = email_id.split('@')[0]
    project_name = project_name.replace("-trigger", "")
    
    try:
        response = ses.send_email(
            Source="eng-team@softmania.in",
            Destination={
                'ToAddresses': [email_id]
            },
            Message={
                'Subject': {
                    'Data': ' Your Environment Has Been Successfully Created',
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': f"""Hi {user_name},

We are pleased to inform you that your requested environment for {project_name} has been successfully created. 

Here are the details:

 Environment Name: {project_name}

If you have any questions or need assistance, please contact labsupport@softmania.in.

Thank you,
Softmania Team
""",
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")
