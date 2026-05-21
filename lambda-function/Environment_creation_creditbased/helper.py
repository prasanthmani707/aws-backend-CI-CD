import boto3
import random
import datetime


def get_splunk_version(body):
    raw = body.get("splunk_version")
    if not raw:
        return ""
    return raw.sub(r"[^a-zA-Z0-9._-]", "", str(raw).strip())

def build_versioned_prefix(base_prefix, splunk_version):
    if not splunk_version:
        return base_prefix
    return f"splunk-version-based-environments/splunk-{splunk_version}/{base_prefix}"

def generate_run_metadata():
    """
    Generates random suffix, timestamp, and ISO current time (UTC).
    """
    suffix = random.randint(100, 999)
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    current_time = (
        datetime.datetime.utcnow()
        .replace(microsecond=0)
        .isoformat() + "Z"
    )

    return suffix, timestamp, current_time