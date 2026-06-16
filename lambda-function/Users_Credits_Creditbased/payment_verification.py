import base64
import json
import urllib.request
import os
import boto3
from decimal import Decimal   
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("Payment_records")  
def payment_verification(order_id, payment_id):
    already_exists = check_payment_db(payment_id)
    if already_exists:
        print("Payment already verified before")
        return False, None,"Payment already processed"

    key_id = os.environ["RAZORPAY_KEY_ID"]
    key_secret = os.environ["RAZORPAY_KEY_SECRET"]
    print("KEY_ID:", key_id)
    print("KEY_SECRET length:", len(key_secret))

    url = f"https://api.razorpay.com/v1/payments/{payment_id}"

    credentials = f"{key_id}:{key_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded_credentials}"
    }

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request) as response:
        payment = json.loads(response.read().decode())

    if payment["status"] == "captured" and payment["order_id"] == order_id:

        amount_paise = payment["amount"]     # amount in paise
        amount_inr = Decimal(str(amount_paise)) / Decimal("100")
        currency = payment["currency"]       # convert to rupees
        save_payment(payment_id,order_id,amount_inr,currency)

        print(f"Payment verified. Amount: {amount_inr} {currency}")

        return True, amount_inr, currency

    return False, 

def check_payment_db(payment_id):
    response = table.get_item(
        Key ={
            "payment_id":payment_id
        }
    )
    if "Item" in response:
        return True
    return False

def save_payment(payment_id,order_id,amount_inr,currency):
    table.put_item(
        Item={
            "payment_id":payment_id,
            "order_id":order_id,
            "amount":amount_inr,
            "currency":currency
        }
    )
