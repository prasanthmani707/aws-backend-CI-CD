import boto3
from decimal import Decimal
from botocore.exceptions import ClientError

ssm = boto3.client('ssm')

PARAMETER_NAME = "/exchange/FixedUSD"

def convert_inr_to_usd(amount_inr):
    try:
        # Get exchange rate from SSM
        response = ssm.get_parameter(
            Name=PARAMETER_NAME
        )

        usd_rate = Decimal(response['Parameter']['Value'])

        # Convert INR → USD
        amount_inr = Decimal(str(amount_inr))
        amount_usd = amount_inr / usd_rate

        # Optional: round to 4 decimals
        Credits = amount_usd
        return round(Credits, 4)

    except ClientError as e:
        print("Error fetching exchange rate:", e)
        raise e