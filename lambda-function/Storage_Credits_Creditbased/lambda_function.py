import boto3
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from boto3.dynamodb.conditions import Key, Attr

# -----------------------
# SETUP
# -----------------------
REGION = "us-east-1"

ec2 = boto3.client("ec2", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)

Credits_rate_catalog = dynamodb.Table("Credits_Rate_Creditbased")
credits_table = dynamodb.Table("Storage_Credits_Creditbased")
instance_registry =dynamodb.Table("instance_registry_creditbased")
logger = logging.getLogger()
logger.setLevel(logging.INFO)
EBS = "EBS#sa-east-1#gp3"

# -----------------------
# HELPERS
# -----------------------
def get_email_id_from_instance(instance_id):
    if instance_id in ("DETACHED", "NULL", None):
        return "NULL", "NULL"

    try:
        resp = ec2.describe_instances(InstanceIds=[instance_id])

        reservations = resp.get("Reservations", [])
        if not reservations:
            return "NULL", "NULL"

        instances = reservations[0].get("Instances", [])
        if not instances:
            return "NULL", "NULL"

        tags = instances[0].get("Tags", [])
        tag_map = {tag["Key"]: tag["Value"] for tag in tags}

        email_id = tag_map.get("UserEmail", "NULL")
        instance_name = tag_map.get("Name", "NULL")

        return email_id, instance_name

    except Exception as e:
        logger.error(f"[{instance_id}] email_id fetch error: {e}")
        return "NULL", "NULL"

def get_volumes_from_instance(instance_id):
    resp = ec2.describe_volumes(
        Filters=[
            {"Name": "attachment.instance-id", "Values": [instance_id]}
        ]
    )
    return resp["Volumes"]


def volume_exists(volume_id):
    resp = credits_table.get_item(Key={"volume_id": volume_id})
    return "Item" in resp


def get_credits(volume_type):
    credits_resp = Credits_rate_catalog.query(
        KeyConditionExpression=Key("resource_type").eq(EBS),
        FilterExpression=Attr("resource_type_name").eq(volume_type)
    )
    if not credits_resp["Items"]:
        logger.warning(f"No Credits found for volume_type={volume_type}")
        return None
    return Decimal(credits_resp["Items"][0]["credits_per_hour"])


# -----------------------
# INSERT NEW VOLUME
# -----------------------
def insert_volume_record(vol, run_time):
    volume_id = vol["VolumeId"]

    if volume_exists(volume_id):
        logger.info(f"[{volume_id}] already exists — skipping insert")
        return

    size_gb = Decimal(str(vol["Size"]))
    volume_type = vol["VolumeType"]
    start_time = vol["CreateTime"].astimezone(timezone.utc)

    attachments = vol.get("Attachments", [])
    instance_id = attachments[0]["InstanceId"] if attachments else "DETACHED"

    email_id, instance_name = get_email_id_from_instance(instance_id)
    email_id = email_id.lower()
    credits_per_gb_hr = get_credits(volume_type)
    if not credits_per_gb_hr:
        logger.warning(f"[{volume_id}] no credits found")
        return

    credits_table.put_item(
        Item={
            "volume_id": volume_id,
            "instance_id": instance_id,
            "instance_name": instance_name,
            "email_id": email_id,
            "volume_type": volume_type,
            "size_gb": size_gb,
            "start_time": start_time.isoformat(),
            "credits_per_gb_hr": credits_per_gb_hr,
            "running_credits": Decimal("0"),
            "status": "ACTIVE",
            "last_updated_time": run_time
        }
    )

    logger.info(f"[{volume_id}] inserted into lifecycle table")

# -----------------------
# UPDATE RUNNING CREDITS
# -----------------------
def update_running_credits(vol, run_time):

    volume_id = vol["VolumeId"]

    item = credits_table.get_item(Key={"volume_id": volume_id}).get("Item")
    if not item:
        return

    size_gb = Decimal(item["size_gb"])
    credits_per_gb_hr = Decimal(item["credits_per_gb_hr"])

    last_update = datetime.fromisoformat(item["last_updated_time"])
    now = datetime.now(timezone.utc)

    duration_seconds = Decimal(int((now - last_update).total_seconds()))
    duration_hours = (duration_seconds / Decimal("3600")).quantize(
        Decimal("0.0000001"), rounding=ROUND_HALF_UP
    )

    incremental_credits = (
        size_gb * credits_per_gb_hr * duration_hours
    ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    credits_table.update_item(
        Key={"volume_id": volume_id},
        UpdateExpression="""
            SET running_credits = if_not_exists(running_credits, :zero) + :inc,
                last_duration_seconds = :dur,
                total_duration_seconds = if_not_exists(total_duration_seconds, :zero) + :dur,
                last_updated_time = :lut
        """,
        ExpressionAttributeValues={
            ":inc": incremental_credits,
            ":dur": duration_seconds,
            ":zero": Decimal("0"),
            ":lut": run_time
        }
    )

    logger.info(f"[{volume_id}] running credits += {incremental_credits}")


# -----------------------
# FINALIZE CREDITS
# -----------------------
def finalize_volume_credits(instance_id):

    resp = credits_table.scan(
        FilterExpression=Attr("instance_id").eq(instance_id)
    )

    items = resp.get("Items", [])
    if not items:
        return

    inst_item = instance_registry.get_item(
        Key={"instance_id": instance_id}
    ).get("Item")

    if not inst_item or not inst_item.get("terminate_time"):
        return

    terminated_time = datetime.fromisoformat(inst_item["terminate_time"])

    for record in items:

        volume_id = record["volume_id"]

        size_gb = Decimal(record["size_gb"])
        credits_per_gb_hr = Decimal(record["credits_per_gb_hr"])
        last_update = datetime.fromisoformat(record["last_updated_time"])

        duration_seconds = max(
            Decimal(0),
            Decimal(int((terminated_time - last_update).total_seconds()))
        )

        duration_hours = (duration_seconds / Decimal("3600")).quantize(
            Decimal("0.0000001"), rounding=ROUND_HALF_UP
        )

        final_increment = (
            size_gb * credits_per_gb_hr * duration_hours
        ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        credits_table.update_item(
            Key={"volume_id": volume_id},
            UpdateExpression="""
                SET running_credits = if_not_exists(running_credits, :zero) + :inc,
                    last_duration_seconds = :dur,
                    total_duration_seconds = if_not_exists(total_duration_seconds, :zero) + :dur,
                    #s = :status,
                    end_time = :end,
                    last_updated_time = :lut
            """,
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":inc": final_increment,
                ":dur": duration_seconds,
                ":zero": Decimal("0"),
                ":status": "DELETED",
                ":end": terminated_time.isoformat(),
                ":lut": terminated_time.isoformat(),
            }
        )
        logger.info(f"[{volume_id}] finalized credits += {final_increment}")

# -----------------------
# LAMBDA HANDLER
# -----------------------
def lambda_handler(event, context):

    run_time = datetime.now(timezone.utc).isoformat()

    try:
        source = event.get("source")
        detail_type = event.get("detail-type")
        detail = event.get("detail", {}) or None
        if isinstance(detail, dict):
            state = detail.get("state")
            instance_id = detail.get("instance-id")
        else:
            state = None
            instance_id = None
        print("FULL EVENT RECEIVED:", event)
        print("EVENT SOURCE:", event.get("source"))
        print("DETAIL TYPE:", event.get("detail-type"))
        print("DETAIL TYPE RAW:", type(event.get("detail")))

        # -----------------------
        # HOURLY SCHEDULE
        # -----------------------
        if event.get("source") in ["aws.scheduler", "aws.events"]:
            volumes = ec2.describe_volumes(
                Filters=[{"Name": "status", "Values": ["in-use"]}]
            )["Volumes"]

            for vol in volumes:
                update_running_credits(vol, run_time)

            return {"status": "HOURLY_UPDATE_DONE"}

        # -----------------------
        # INSTANCE RUNNING
        # -----------------------
        if state == "running":
            volumes = get_volumes_from_instance(instance_id)

            for vol in volumes:
                insert_volume_record(vol, run_time)

            return {"status": "RUNNING_INSERT_DONE"}

        # -----------------------
        # INSTANCE TERMINATING
        # -----------------------
        if "Records" in event:
            for record in event["Records"]:
                if record["eventName"] != "MODIFY":
                    continue

            new_image = record["dynamodb"].get("NewImage", {})
            old_image = record["dynamodb"].get("OldImage", {})

            old_term = old_image.get("terminate_time", {}).get("S")
            new_term = new_image.get("terminate_time", {}).get("S")

        # Run finalize only if terminate_time changed from null → set
            if not old_term and new_term:
                instance_id = new_image["instance_id"]["S"]
                finalize_volume_credits(instance_id)

    except Exception as e:
        logger.exception(f"Lambda failure: {e}")
        return {"status": "ERROR", "message": str(e)}