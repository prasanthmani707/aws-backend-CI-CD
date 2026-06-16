import json
import boto3
from decimal import Decimal
from datetime import datetime
import uuid
import urllib.request
from botocore.exceptions import ClientError
from check_user_exists import check_user_exists
from send_wallet_credit_email import send_wallet_credit_email
from welcome_email import send_welcome_email
from converter_inr_to_usd import convert_inr_to_usd
from payment_verification import payment_verification
from auth_utils import get_email_from_event
from converter_usd_to_credits import convert_usd_to_credits,Fixedrate
from cach import track_container_requests
# DynamoDB table
dynamodb = boto3.resource('dynamodb')
credit_table = dynamodb.Table('Users_Credits_Creditbased')

# Lambda client (to send record to Ledger)
lambda_client = boto3.client('lambda')
LEDGER_LAMBDA_NAME = "history_tracker_creditbased"  # 👈 Your ledger Lambda name
cached_rate = None 

def lambda_handler(event, context):
    global cached_rate
    try:
        email_id, error = get_email_from_event(event)
        print(f"email id : {email_id}")

        if error:
            return error

        # 1️⃣ Parse request body
        body = event.get('body')
        if isinstance(body, str):
            body = json.loads(body)
        current_request_count , container_id = track_container_requests(context)    
        if cached_rate is None:
            print(f"🔄 FIRST TIME - Fetching SSM in container {container_id[:8]} (Req #{current_request_count})")
            cached_rate = Fixedrate()
        else:
            print(f"✅ Using CACHE in container {container_id[:8]} (Req #{current_request_count})")
        
        order_id = body.get('order_id')
        payment_id = body.get('payment_id')
        print(f"{payment_id}")
        print(f"{order_id}")
        # amount_inr = body.get('amount')
        txn_type = body.get('type', '').upper()

        verified, razorpay_amount ,currency = payment_verification(order_id, payment_id)
        print(f"verify pay :{razorpay_amount} currency: {currency}")
        if not verified:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Payment verification failed'})
            }
        amount = Decimal(str(razorpay_amount))
        print(f" Paid amount {amount}")
        if currency == "USD":
            Credits = convert_usd_to_credits(amount,cached_rate)
        else:
            amount_usd = convert_inr_to_usd(amount)
            print(f"usd : {amount_usd}")
            Credits = convert_usd_to_credits(amount_usd,cached_rate)


        # 2️⃣ Validation
        if not all([email_id, Credits, txn_type]):
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing fields'})
            }

        if txn_type != 'PAY':
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Only PAY transactions allowed'})
            }
        Credits = Decimal(str(Credits))
        if Credits <= 0:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'credits must be positive'})
            }
        updated_time = datetime.utcnow().isoformat() 
        # 3️⃣ Update Credits
        is_existing_user = check_user_exists(email_id)

        response = credit_table.update_item(
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
        if not is_existing_user:
            send_welcome_email(email_id,Credits)
        else:
            send_wallet_credit_email(email_id, Credits)

        prev_credits = response["Attributes"].get("previous_credits", Decimal("0"))
        curr_credits = response["Attributes"].get("current_credits", Decimal("0"))

        # 4️⃣ Prepare ledger record
        ledger_record = {
            "tnx_id": str(uuid.uuid4()),
            "email_id": email_id,
            "Credits": float(Credits),
            "credits_before": float(prev_credits),
            "credits_after": float(curr_credits),
            "source": "PAY",
            "txn_type":currency,
            "status": "SUCCESS",
            "updated_time": updated_time,  # ✅ added here
        }

        # 5️⃣ Invoke ledger Lambda async with logging
        try:
            payload = {"records": [ledger_record]}
            print(f"🚀 Invoking ledger Lambda '{LEDGER_LAMBDA_NAME}' with payload:")
            print(json.dumps(payload, indent=2))

            response = lambda_client.invoke(
                FunctionName=LEDGER_LAMBDA_NAME,
                InvocationType='Event',  # async
                Payload=json.dumps(payload).encode('utf-8')
            )
            if response['StatusCode'] != 202:
                print("⚠️ Unexpected status code from Lambda invoke:", response['StatusCode'])
            else:
                print("✅ Ledger update initiated successfully")

        except ClientError as e:
            print("❌ Failed to invoke ledger Lambda:", e)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'PAY successful',
                'Credits': float(Credits),
                'Credits_before': float(prev_credits),
                'Credits_after': float(curr_credits),
                'updated_time': updated_time  # ✅ include in response
            })
        }

    except ClientError as e:
        print("AWS ClientError:", e)
        return {'statusCode': 500, 'body': json.dumps({'message': 'AWS Error'})}

    except Exception as e:
        print("Internal Error:", e)
        return {'statusCode': 500, 'body': json.dumps({'message': 'Internal Server Error'})}
