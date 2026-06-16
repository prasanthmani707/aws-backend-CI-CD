from decimal import Decimal
import boto3

# Initialize client outside the functions to reuse the connection
ssm = boto3.client('ssm')
PARAMETER_NAME = "/exchange/Fixedrate"

def Fixedrate():
    # Fixed indentation: 'Fix_rate' and 'return' should be aligned with 'response'
    response = ssm.get_parameter(Name=PARAMETER_NAME)
    fix_rate = Decimal(response['Parameter']['Value'])
    return fix_rate

def convert_usd_to_credits(amount_usd, cached_rate):
    # Ensure inputs are Decimal for precise financial calculations
    amount = Decimal(str(amount_usd))
    credits = amount * cached_rate
    return credits