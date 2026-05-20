import json
import re 
import boto3
import random
import datetime
from helper import generate_run_metadata
from helper import get_splunk_version, build_versioned_prefix

import logging
s3 = boto3.client("s3")
BUCKET = "splunklab-dev"

codebuild = boto3.client("codebuild")
dynamodb = boto3.resource("dynamodb")
status_table = dynamodb.Table("User_environment_history_creditbased")


def process_template_file(
    template_file,
    body,
    triggered_projects,
    splunk_version,
    soar_install,
    install_splunk,
    botsv3,
    usermail,
    course_id,
    unique_id="",
    start_date="",
):
    suffix, timestamp, current_time = generate_run_metadata()
    template_file_lower = template_file.lower()

    s3_key_prefix = (
        "tfvars/" if any(x in template_file for x in ["DNC", "SE", "DC", "SOAR", "Splunk-DNC_SHIDXHF"]) else "sds-tfvars/"
    )
    s3_key_prefix = build_versioned_prefix(s3_key_prefix, splunk_version)

    print("📥 Fetching template from S3:", f"{s3_key_prefix}{template_file}")
    res = s3.get_object(Bucket=BUCKET, Key=f"{s3_key_prefix}{template_file}")
    content = res["Body"].read().decode()
    print(f"📄 Template content fetched, size: {len(content)} characters")

    if "{current_time}" in content:
        content = content.replace("{current_time}", current_time)

    placeholders = re.findall(r"{(.*?)}", content)
    for key in placeholders:
        if key == "PlanStartDate":
            value = current_time
        elif key == "suffix":
            value = str(suffix)
        elif key in ["course_id", "CourseID", "COURSE_ID"]:
            value = body.get("course_id") or "General"
        else:
            value = str(body.get(key, f"<{key}_missing>"))
        content = content.replace(f"{{{key}}}", value)

    final_key_prefix = "final" if "tfvars/" in s3_key_prefix else "sds-final"
    final_key = (
        f"{final_key_prefix}/terraform-{timestamp}-{suffix}-"
        f"{template_file.replace('.tfvars', '')}.tfvars"
    )

    s3.put_object(Bucket=BUCKET, Key=final_key, Body=content.encode())
    print(f"✅ Final tfvars saved as: {final_key}")

    # 🔍 Determine project name
    if any(x in template_file for x in ["DNC", "SE", "DC", "SOAR", "Splunk-DNC_SHIDXHF"]):
        template_type = next((x for x in ["DNC", "SE", "DC", "SOAR", "Splunk-DNC_SHIDXHF"] if x in template_file), None)
        if not template_type:
            return None

        if template_type == "DNC":
            if botsv3 == "yes" and install_splunk == "yes":
                project_name = "Splunk-DNC-EC2Splunk-Ansible"
            elif botsv3 == "yes":
                project_name = "Splunk-DNC-EC2Only"
            elif install_splunk == "yes":
                project_name = "Splunk-DNC-EC2Splunk"
            else:
                project_name = "Splunk-DNC-EC2Only"

        elif template_type in ["SE", "HF", "MC"]:
            if botsv3 == "yes" and install_splunk == "yes":
                project_name = "SplunkEC2Ansible"
            elif botsv3 == "yes":
                project_name = "SplunkEC2Only"
            elif install_splunk == "yes":
                project_name = "SplunkEC2Splunk"
            else:
                project_name = "SplunkEC2Only"

        elif template_type in ["Splunk-DNC_SHIDXHF"]:
            project_name = (
                "Splunk-DNC_SHIDXHF-WS-trigger" if install_splunk == "yes" else "Splunk-DNC_SHIDXHF-WOS-trigger"
            )

        elif template_type == "DC":
            project_name = (
                "Splunk-DC-EC2Splunk" if install_splunk == "yes" else "Splunk-DC-EC2Only"
            )
            
        elif template_type == "SOAR":
            if soar_install not in {"yes", "no"}:
                raise ValueError("For Splunk-SOAR template, soar_install must be 'yes' or 'no'.")
            if soar_install == "yes":
                project_name = "Splunk-SOAR-trigger"
            else:
                project_name = "Splunk-SOAR-ec2-only-trigger"
    else:
        if "mysql" in template_file_lower:
            project_name = "MySQL-trigger"
        elif "mssql" in template_file_lower:
            project_name = "MSSQL-trigger"
        elif "ossec" in template_file_lower:
            project_name = "OSSEC-trigger"
        elif "syslog" in template_file_lower:
            project_name = "Syslog-trigger"
        elif "jenkins" in template_file_lower:
            project_name = "Jenkins-trigger"
        elif "linux" in template_file_lower:
            project_name = "Linux-trigger"
        elif "openvpn" in template_file_lower:
            project_name = "OpenVPN-trigger"
        else:
            raise ValueError(f"Unknown template type: {template_file}")

    print(f"🚀 Triggering CodeBuild: {project_name}")

    response = codebuild.start_build(
        projectName=project_name,
        environmentVariablesOverride=[
            {"name": "TFVARS_S3_KEY", "value": final_key, "type": "PLAINTEXT"},
            {"name": "USER_EMAIL", "value": usermail, "type": "PLAINTEXT"},
            {"name": "COURSE_ID", "value": course_id, "type": "PLAINTEXT"},
            {"name": "TEMPLATE_FILE", "value": template_file, "type": "PLAINTEXT"},
            {"name": "UNIQUE_ID", "value": unique_id, "type": "PLAINTEXT"},
            {"name": "START_DATE", "value": start_date, "type": "PLAINTEXT"},
            {"name": "ITEM_ID", "value": body.get("id", ""), "type": "PLAINTEXT"},
        ],
    )

    actual_build_id = response["build"]["id"]

    status_table.put_item(
        Item={
            "email_id": usermail,
            "build_id": actual_build_id,
            "labs_type": f"{body.get('lab_category', 'custom-labs')}#{datetime.datetime.utcnow().isoformat()}",
            "status": "in_progress",
             "course_id":course_id,
            "environment_name": project_name,
            "lab_category": body.get("lab_category"),
            "instance_ids": [],
            "created_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat(),
        }
    )

    return {
        "template": template_file,
        "final_tfvars": final_key,
        "codebuild_project": project_name,
        "actual_build_id": actual_build_id,
    }