import boto3
import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from boto3.dynamodb.conditions import Key

# =========================
# CONFIG
# =========================
PRICING_REGION = "us-east-1"
LOCATION = "US East (N. Virginia)"
DYNAMODB_TABLE = "Pricing_catalog_creditbased"

INSTANCE_TYPES = [
    "t3.medium",
    "t3.large",
    "t3.xlarge",
    "m4.large",
    "m4.xlarge"
]

HOURS_PER_MONTH = Decimal("730")

# =========================
# PERCENTAGES
# =========================
MEMBERSHIP_PERCENT = Decimal("33")
MANAGEMENT_PERCENT = Decimal("30")

pricing = boto3.client("pricing", region_name=PRICING_REGION)
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DYNAMODB_TABLE)

# =========================
# UTILS
# =========================
def round_price(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


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

# ======================================================
# ================= EC2 PRICING =========================
# ======================================================
def get_ec2_price(instance_type):
    response = pricing.get_products(
        ServiceCode="AmazonEC2",
        Filters=[
            {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
            {"Type": "TERM_MATCH", "Field": "location", "Value": LOCATION},
            {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
            {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
            {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
            {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"}
        ],
        MaxResults=1
    )

    price_item = json.loads(response["PriceList"][0])
    terms = price_item["terms"]["OnDemand"]

    for term in terms.values():
        for dim in term["priceDimensions"].values():
            base_hour = round_price(Decimal(dim["pricePerUnit"]["USD"]))
            base_month = round_price(base_hour * HOURS_PER_MONTH)

            return (
                calculate_breakdown(base_hour),
                calculate_breakdown(base_month)
            )

    return None, None


def save_ec2(instance_type, hourly, monthly):
    now = datetime.utcnow().isoformat() + "Z"
    pk = f"ec2#us-east-1#{instance_type}"

    table.put_item(
        Item={
            "resource_type": pk,
            "resource_type_name": "ec2",
            "instance_type": instance_type,
            "region": "us-east-1",

            "aws_price_per_hour": str(hourly["base_price"]),
            "membership_percent": str(hourly["membership_percent"]),
            "management_percent": str(hourly["management_percent"]),
            "final_price_per_hour": str(hourly["final_price"]),
            "final_price_per_month": str(monthly["final_price"]),
            "pricing_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# ======================================================
# ================= EBS GP3 PRICING =====================
# ======================================================
def get_gp3_price():
    response = pricing.get_products(
        ServiceCode="AmazonEC2",
        Filters=[
            {"Type": "TERM_MATCH", "Field": "volumeType", "Value": "General Purpose"},
            {"Type": "TERM_MATCH", "Field": "usagetype", "Value": "EBS:VolumeUsage.gp3"},
            {"Type": "TERM_MATCH", "Field": "location", "Value": LOCATION}
        ],
        MaxResults=1
    )

    price_item = json.loads(response["PriceList"][0])
    terms = price_item["terms"]["OnDemand"]

    for term in terms.values():
        for dim in term["priceDimensions"].values():
            base_price = Decimal(dim["pricePerUnit"]["USD"]).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            return calculate_breakdown(base_price)

    return None

# ======================================================
# ================= LAMBDA HANDLER ======================
# ======================================================
def lambda_handler(event, context):
    results = []

    # ---------- EC2 ----------
    for instance in INSTANCE_TYPES:
        hourly, monthly = get_ec2_price(instance)
        save_ec2(instance, hourly, monthly)

        results.append({
            "resource": "ec2",
            "instance": instance,
            "final_hourly": str(hourly["final_price"]),
            "final_monthly": str(monthly["final_price"])
        })

    # ---------- EBS ----------
    ebs = get_gp3_price()
    if not ebs:
        raise Exception("EBS gp3 price not found")

    ebs_hour = (ebs["final_price"] / HOURS_PER_MONTH).quantize(
        Decimal("0.00000001"), rounding=ROUND_HALF_UP
    )

    table.put_item(
        Item={
            "resource_type": "EBS",
            "resource_type_name": "gp3",
            "region": "us-east-1",
            "aws_price_per_hour": str(ebs["base_price"]),
            "membership_percent": str(ebs["membership_percent"]),
            "management_percent": str(ebs["management_percent"]),
            "final_price_per_month": str(ebs["final_price"]),
            "final_price_per_hour": str(ebs_hour),

            "pricing_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

    results.append({
        "resource": "EBS",
        "final_gb_month": str(ebs["final_price"])
    })

    return {
        "statusCode": 200,
        "body": results
    }