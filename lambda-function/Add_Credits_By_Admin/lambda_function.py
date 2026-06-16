import json
import boto3
from decimal import Decimal
from datetime import datetime
import uuid
from botocore.exceptions import ClientError

from check_user_exists import check_user_exists
from send_credit_email import send_credit_email
from welcome_email import send_welcome_email
from admin_verify_email import admin_verify_email
from converter import convert_usd_to_credits, convert_credits_to_usd, Fixedrate, convert_inr_to_usd
from cach import track_container_requests   # ⚠️ keep as 'cach' if that's your file name
from zohosheetupdate import zohosheetupdate

# DynamoDB
dynamodb = boto3.resource('dynamodb')
credits_table = dynamodb.Table('Users_Credits_Creditbased')

# Lambda client (Ledger)
lambda_client = boto3.client('lambda')
LEDGER_LAMBDA_NAME = "history_tracker_creditbased"

cached_rate = None


def lambda_handler(event, context):
    global cached_rate
    try:

        # 1️⃣ Parse request body
        body = event.get('body')

        if body is None:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Body is missing'})
            }

        if isinstance(body, str):
            body = json.loads(body)

        current_request_count, container_id = track_container_requests(context)

        if cached_rate is None:
            print(f"🔄 FIRST TIME - Fetching SSM in container {container_id[:8]} (Req #{current_request_count})")
            cached_rate = Fixedrate()
        else:
            print(f"✅ Using CACHE in container {container_id[:8]} (Req #{current_request_count})")

        email_id = body.get('email_id')
        amount_inr = body.get('amount')
        Credits = body.get('Credits')

        # ✅ FIX: default reason
        reason = body.get('reason', 'No reason provided')

        admin_email = body.get('admin_email')
        txn_type = body.get('type', '').upper()

        if email_id:
            email_id = email_id.lower()

        print("Email:", email_id)
        print("Amount INR:", amount_inr)

        # 2️⃣ Validation
        if not all([email_id, txn_type]):
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing required fields'})
            }

        if txn_type != 'PAY':
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Only PAY transactions allowed'})
            }

        # 3️⃣ Convert INR → Credits
        if not Credits:
            if amount_inr <= 0:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'message': 'amount must be positive'})
                }

            amount_inr = Decimal(str(amount_inr))
            amount_usd = convert_inr_to_usd(amount_inr)
            Credits = convert_usd_to_credits(amount_usd)
            Credits = Decimal(str(Credits))

            print(f"admin not send the Credits, converted USD {amount_usd}")
        else:
            print(f"admin sent Credits directly: {Credits}")
            Credits = Decimal(str(Credits))
            amount_usd = convert_credits_to_usd(Credits)

        print(f"admin credits added: {Credits}")

        updated_time = datetime.utcnow().isoformat()

        # 4️⃣ Check user
        is_existing_user, existing_credits = check_user_exists(email_id)

        # 5️⃣ Update credits in DB
        response = credits_table.update_item(
            Key={'email_id': email_id},
            UpdateExpression="""
                SET previous_credits = if_not_exists(current_credits, :zero),
                    current_credits = if_not_exists(current_credits, :zero) + :Credits,
                    last_transaction_Credit = :Credits,
                    cb_last_updated = :now
            """,
            ExpressionAttributeValues={
                ':Credits': Credits,
                ':zero': Decimal('0'),
                ':now': updated_time
            },
            ReturnValues="UPDATED_NEW"
        )

        attributes = response.get("Attributes") or {}

        prev_credits = attributes.get("previous_credits", Decimal("0"))
        curr_credits = attributes.get("current_credits", Decimal("0"))

        print(f"✅ credits updated for {email_id}: {prev_credits} → {curr_credits}")

        # 6️⃣ Emails
        print(f"${existing_credits} = ₹{existing_credits}")

        if not is_existing_user:
            send_welcome_email(email_id, Credits)
        else:
            send_credit_email(email_id, Credits, existing_credits)

        admin_verify_email(email_id, Credits, admin_email, existing_credits, reason)

        # ✅ FIX: Correct Zoho call with parameters
        zohosheetupdate(email_id,Credits,admin_email,reason)

        # 7️⃣ Ledger Record
        ledger_record = {
            "tnx_id": str(uuid.uuid4()),
            "email_id": email_id,
            "Credits": float(Credits),
            "credits_before": float(prev_credits),
            "credits_after": float(curr_credits),
            "source": "PAY",
            "status": "SUCCESS",
            "updated_time": updated_time,
        }

        # 8️⃣ Invoke Ledger Lambda
        try:
            payload = {"records": [ledger_record]}

            print("🚀 Invoking Ledger Lambda")
            print(json.dumps(payload, indent=2))

            invoke_response = lambda_client.invoke(
                FunctionName=LEDGER_LAMBDA_NAME,
                InvocationType='Event',
                Payload=json.dumps(payload).encode('utf-8')
            )

            if invoke_response['StatusCode'] != 202:
                print("⚠️ Unexpected Status:", invoke_response['StatusCode'])
            else:
                print("✅ Ledger update triggered")

        except ClientError as e:
            print("❌ Ledger Lambda Error:", e)

        # 9️⃣ Success response
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'PAY successful',
                'credited_credits': float(Credits),
                'credits_before': float(prev_credits),
                'credits_after': float(curr_credits),
                'updated_time': updated_time
            })
        }

    except ClientError as e:
        print("AWS ClientError:", e)

        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'AWS Error'})
        }

    except Exception as e:
        print("Internal Error:", e)

        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal Server Error'})
        }