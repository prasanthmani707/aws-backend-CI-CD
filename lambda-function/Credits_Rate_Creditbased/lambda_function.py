import boto3
import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from converter_usd_tocredits import convert_usd_to_credits, Fixedrate
from cach import track_container_requests

# =========================
# CONFIG
# =========================
PRICING_REGION = "us-east-1"

REGION_TO_LOCATION = {
    "sa-east-1": "South America (Sao Paulo)"
}

REGIONS = ["sa-east-1"]

DYNAMODB_TABLE = "Credits_Rate_Creditbased"

with open("config.json") as f:
    config = json.load(f)

MEMBERSHIP_PERCENT = Decimal(str(config["membership_percent"]))
MANAGEMENT_PERCENT = Decimal(str(config["management_percent"]))
PLATFORM_cost = Decimal(str(config["platform_credits"]))

INSTANCE_TYPES = ["t3.medium", "t3.large", "t3.xlarge", "m4.large", "m4.xlarge"]

HOURS_PER_MONTH = Decimal("730")
DAYS_PER_MONTH = Decimal("30")

# =========================
# AWS CLIENTS
# =========================
pricing = boto3.client("pricing", region_name=PRICING_REGION)
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DYNAMODB_TABLE)
cached_rate = None 

# =========================
# UTILS
# =========================
def round_price(val: Decimal, places: str = "0.0001") -> Decimal:
    return val.quantize(Decimal(places), rounding=ROUND_HALF_UP)

def calculate_breakdown(base_price: Decimal):

    membership_cost = round_price(base_price * MEMBERSHIP_PERCENT / Decimal("100"))
    management_cost = round_price(base_price * MANAGEMENT_PERCENT / Decimal("100"))

    final_price = round_price(base_price + membership_cost + management_cost)

    return {
        "base_price": base_price,
        "membership_percent": MEMBERSHIP_PERCENT,
        "management_percent": MANAGEMENT_PERCENT,
        "membership_cost": membership_cost,
        "management_cost": management_cost,
        "final_price": final_price
    }

# =========================
# EC2 PRICING
# =========================
def get_ec2_price(instance_type, location):

    response = pricing.get_products(
        ServiceCode="AmazonEC2",
        Filters=[
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "RHEL"},
            {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
            {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
            {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"}
        ],
        MaxResults=1
    )

    if not response["PriceList"]:
        print(f"No EC2 pricing found for {instance_type} in {location}")
        return None, None

    price_list = json.loads(response["PriceList"][0])
    terms = price_list.get("terms", {}).get("OnDemand", {})

    for term in terms.values():
        for dim in term.get("priceDimensions", {}).values():

            base_hour = round_price(Decimal(dim["pricePerUnit"]["USD"]))
            base_month = round_price(base_hour * HOURS_PER_MONTH)

            return calculate_breakdown(base_hour), calculate_breakdown(base_month)

    return None, None

def save_ec2(region_code, instance_type, hourly, monthly):

    now = datetime.utcnow().isoformat()
    pk = f"ec2#{region_code}#{instance_type}"
    final_price_hourly = hourly["final_price"] if hourly else None
    credits_per_hour = convert_usd_to_credits(final_price_hourly,cached_rate)
    platform_credits = convert_usd_to_credits(PLATFORM_cost,cached_rate)if PLATFORM_cost is not None else None
    table.put_item(
        Item={
            "resource_type": pk,
            "resource_type_name": "ec2",
            "instance_type": instance_type,
            "region": region_code,
            "aws_price_per_hour": str(hourly["base_price"]) if hourly else None,
            "membership_percent": str(hourly["membership_percent"]) if hourly else None,
            "management_percent": str(hourly["management_percent"]) if hourly else None,
            "platform_cost": str(PLATFORM_cost),
            "platform_credits":str(platform_credits) if platform_credits is not None else None,
            "final_price_hourly": str(hourly["final_price"]) if hourly else None,
            "credits_per_hour": str(credits_per_hour) if credits_per_hour is not None else None,
            # "final_credits_per_month": str(monthly["final_price"]) if monthly else None,
            "pricing_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "timestamp": now
        }
    )

# =========================
# EBS GP3 PRICING
# =========================
def get_gp3_price(location):

    response = pricing.get_products(
        ServiceCode="AmazonEC2",
        Filters=[
            {"Type": "TERM_MATCH", "Field": "volumeApiName", "Value": "gp3"},
            {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Storage"},
            {"Type": "TERM_MATCH", "Field": "location", "Value": location}
        ],
        MaxResults=1
    )

    if not response["PriceList"]:
        print(f"No EBS GP3 pricing found in {location}")
        return None

    price_item = json.loads(response["PriceList"][0])
    terms = price_item["terms"]["OnDemand"]

    for term in terms.values():
        for dim in term["priceDimensions"].values():

            base_price = Decimal(dim["pricePerUnit"]["USD"]).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )

            return base_price

    return None

def save_ebs(region_code):

    now = datetime.utcnow().isoformat()
    location = REGION_TO_LOCATION[region_code]

    api_month_price = get_gp3_price(location)

    if api_month_price is None:
        print(f"Skipping EBS pricing in {region_code}")
        return

    aws_price_per_hour = round_price(api_month_price / HOURS_PER_MONTH, "0.00000001")

    # Apply percentages ONLY to AWS price
    membership_cost = round_price(
        aws_price_per_hour * MEMBERSHIP_PERCENT / Decimal("100"), "0.00000001"
    )
    management_cost = round_price(
        aws_price_per_hour * MANAGEMENT_PERCENT / Decimal("100"), "0.00000001"
    )

    final_price_per_hour = round_price(
        aws_price_per_hour + membership_cost + management_cost,
        "0.00000001"
    )

    # Monthly calculation
    aws_month = aws_price_per_hour * HOURS_PER_MONTH

    membership_month = round_price(
        aws_month * MEMBERSHIP_PERCENT / Decimal("100")
    )
    management_month = round_price(
        aws_month * MANAGEMENT_PERCENT / Decimal("100")
    )

    final_price_per_month = round_price(
        aws_month + membership_month + management_month
    )
    final_price_hourly = final_price_per_hour  # keep as number
    platform_credits = convert_usd_to_credits(PLATFORM_cost,cached_rate)if PLATFORM_cost is not None else None
    credits_per_hour = convert_usd_to_credits(final_price_hourly,cached_rate) if final_price_hourly is not None else None
    table.put_item(
        Item={
            "resource_type": f"EBS#{region_code}#gp3",
            "resource_type_name": "gp3",
            "instance_type": None,
            "region": region_code,
            "aws_price_per_hour": str(aws_price_per_hour),
            "membership_percent": str(MEMBERSHIP_PERCENT),
            "management_percent": str(MANAGEMENT_PERCENT),
            "platform_cost": str(PLATFORM_cost),
            "platform_credits":str(platform_credits) if platform_credits is not None else None,
            "final_price_hourly": str(final_price_per_hour),
            "credits_per_hour": str(credits_per_hour) if credits_per_hour is not None else None,
            # "final_credits_per_month": str(final_price_per_month),
            "pricing_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "timestamp": now
        }
    )
# =========================
# LAMBDA HANDLER
# =========================
def lambda_handler(event, context):
    global cached_rate
    results = []
    current_request_count , container_id = track_container_requests(context)    
    if cached_rate is None:
        print(f"🔄 FIRST TIME - Fetching SSM in container {container_id[:8]} (Req #{current_request_count})")
        cached_rate = Fixedrate()
    else:
        print(f"✅ Using CACHE in container {container_id[:8]} (Req #{current_request_count})")

    for region_code in REGIONS:

        location = REGION_TO_LOCATION[region_code]

        # EC2 Pricing
        for instance in INSTANCE_TYPES:

            hourly, monthly = get_ec2_price(instance, location)

            save_ec2(region_code, instance, hourly, monthly)

            results.append({
                "resource_type": f"ec2#{region_code}#{instance}",
                "resource_type_name": "ec2",
                "instance_type": instance,
                "region": region_code
            })

        # EBS Pricing
        save_ebs(region_code)

        results.append({
            "resource_type": f"EBS#{region_code}#gp3",
            "resource_type_name": "gp3",
            "region": region_code
        })

    return {
        "statusCode": 200,
        "body": results
    }