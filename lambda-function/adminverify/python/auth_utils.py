import json

def get_email_from_event(event):
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
        email_id = claims.get("email")

        if not email_id:
            return None, {
                'statusCode': 401,
                'body': json.dumps('Unauthorized: email not found in token')
            }

        return email_id, None

    except Exception:
        return None, {
            'statusCode': 400,
            'body': json.dumps('Invalid Request')
        }