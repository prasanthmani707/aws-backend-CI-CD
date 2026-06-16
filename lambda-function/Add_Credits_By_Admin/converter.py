import boto3
from decimal import Decimal
from botocore.exceptions import ClientError

ssm = boto3.client('ssm')

PARAMETER_NAME = "/exchange/inr_to_usd"
# Initialize client outside the functions to reuse the connection
PARAMETER_NAME_fixed = "/exchange/Fixedrate"
def Fixedrate():
    # Fixed indentation: 'Fix_rate' and 'return' should be aligned with 'response'
    response = ssm.get_parameter(Name=PARAMETER_NAME_fixed)
    fix_rate = Decimal(response['Parameter']['Value'])
    return fix_rate

def convert_usd_to_credits(amount_usd):
    amount = Decimal(str(amount_usd))
    credits = amount * Decimal("100")
    return credits

def convert_credits_to_usd(Credits):
    Credit = Decimal(str(Credits))
    amount_usd = Credit / 100
    return amount_usd

def convert_inr_to_usd(amount_inr):
    try:
        # Get exchange rate from SSM
        response = ssm.get_parameter(
            Name=PARAMETER_NAME
        )

        usd_rate = Decimal(response['Parameter']['Value'])

        # Convert INR → USD
        amount_inr = Decimal(str(amount_inr))
        amount_usd = amount_inr * usd_rate

        # Optional: round to 4 decimals
        return round(amount_usd, 4)

    except ClientError as e:
        print("Error fetching exchange rate:", e)
        raise e