import json
import re
import boto3
import random
import datetime
from helper import generate_run_metadata
from helper import get_splunk_version, build_versioned_prefix

s3 = boto3.client("s3")
codebuild = boto3.client("codebuild")
dynamodb = boto3.resource("dynamodb")
status_table = dynamodb.Table("User_environment_history_creditbased")

BUCKET = "splunklab-dev"

print("✅ LOADED project_based_labs.py")


# ✅ Separated handler for direct triggers
def handle_direct_triggers(body, triggered_projects):
    extra_direct_triggers = {
        # template_name: (codebuild_project, tfvars_folder)
        "Splunk-DC_IDX_SS": ("Splunk-DC-IDX-SS-trigger", "tfvars/"),
        "Splunk-SE_DEV_ADV_KO": ("Splunk-SE_DEV_ADV_KO-trigger", "tfvars/"),
        "Splunk-DNC_DATA_ADMIN_ADV1": ("Splunk-DNC-EC2Only","tfvars/"),
        "Splunk-DC_IDX_MS_SH": ("Splunk-DC_IDX_MS_SH-trigger","tfvars/"),
        "Splunk-DC_IDX_SS_SH": ("Splunk-DC_IDX_SS_SH-trigger","tfvars/"),
        "Splunk-DC_IDX_SS_SHC_SS": ("Splunk-DC_IDX_SS_SHC_SS-trigger","tfvars/"),
        "Splunk-DC_IDX_MS_SHC_MS": ("Splunk-DC_IDX_MS_SHC_MS-trigger","tfvars/"),
        "Splunk-DC-SS-Full": ("Splunk-DC-SS-Full-trigger","tfvars/"),
        "Splunk-HF": ("SplunkEC2Only","tfvars/"),
        "Splunk-MC": ("SplunkEC2Only","tfvars/"),
        "Splunk-DC_IDX_SS_NS": ("Splunk-DC_IDX_SS_NS-trigger", "tfvars/"),
        "Splunk-DC_IDX_SS_S1": ("Splunk-DC_IDX_SS_S1-trigger", "tfvars/"),
        "Splunk-DC_IDX_SS_S2": ("Splunk-DC_IDX_SS_S2-trigger", "tfvars/"),
        "Splunk-DC_SH_SS_S2": ("Splunk-DC_SH_SS_S2-trigger", "tfvars/"),
        "Splunk-DC_S2_IDXC_SH": ("Splunk-DC_S2_IDXC_SH-trigger", "tfvars/"),
        "Splunk-DC_S2_SHC": ("Splunk-DC_SH_SS_S2-trigger", "tfvars/"),
        "Splunk-DNC_SHIDXHF" : ("Splunk-DNC_SHIDXHF-WOS-trigger", "tfvars/"),
        "windows-ad-dns": ("Windows-AD-DNS-trigger", "sds-tfvars/"),
        "windows-client": ("Windows-trigger", "sds-tfvars/"),
        "windows-ad-dns-client": ("Windows-AD-DNS-Client-trigger", "sds-tfvars/"),
        "Splunk-DC-ADPL": ("Splunk-DC-ADPL-trigger", "tfvars/"),
        "Splunk-DC-ST-UF":("Splunk-DC-ST-UF-trigger", "tfvars/"),
        # Add future direct templates here...
    }

    template_files = body.get("template_file", [])
    if isinstance(template_files, str):
        try:
            template_files = json.loads(template_files)
        except:
            template_files = [template_files]

    suffix, timestamp, current_time = generate_run_metadata()
    splunk_version = get_splunk_version(body)

    # ✅ MODIFIED: Check if this is normal user access (all three fields missing)
    id_field = body.get("id")
    unique_id_field = body.get("unique_id")
    course_id = body.get('course_id')
    is_normal_user_access = all([not id_field, not unique_id_field])

    for template_name in template_files:
        # Normalize both numbered and plain template filenames.
        # Examples:
        # "Splunk-DC_IDX_SS_SHC_SS-670.template" -> "Splunk-DC_IDX_SS_SHC_SS"
        # "windows-client.template" -> "windows-client"
        template_base = re.sub(r'(?:-\d+)?\.template$', '', template_name).strip()
        
        for direct_key, (project_name, tfvars_prefix) in extra_direct_triggers.items():
            if direct_key == template_base:
                # Splunk-SOAR requires an explicit yes/no toggle.
                if direct_key == "Splunk-SOAR":
                        # Default "yes" instead of "no"
                    soar_install = str(body.get("soar_install", "no")).strip().lower()
                    if soar_install not in ["yes", "no"]:
                         raise ValueError("For Splunk-SOAR template, provide soar_install as 'yes' or 'no'")
                    project_name = "Splunk-SOAR-trigger" if soar_install == "yes" else "Splunk-SOAR-ec2-only-trigger"

                # ✅ MODIFIED: Only validate required fields if NOT normal user access
                if not is_normal_user_access:
                    required_fields = ["id", "unique_id"]
                    missing_fields = []
                    
                    for field in required_fields:
                        if not body.get(field):
                            missing_fields.append(field)
                    
                    if missing_fields:
                        error_msg = f"Missing required fields for direct trigger: {', '.join(missing_fields)}"
                        print(f"❌ {error_msg}")
                        raise ValueError(error_msg)
                else:
                    print(f"📝 Normal user access detected for direct template {template_name}, skipping validation")
                
                versioned_tfvars_prefix = build_versioned_prefix(tfvars_prefix, splunk_version)
                print(f"📥 Fetching direct template: {versioned_tfvars_prefix}{template_name}")
                try:
                    res = s3.get_object(Bucket=BUCKET, Key=f"{versioned_tfvars_prefix}{template_name}")
                    content = res['Body'].read().decode()
                except Exception as e:
                    print(f"❌ Failed to fetch template {template_name}: {str(e)}")
                    continue

                # 🔁 Replace placeholders
                if "{current_time}" in content:
                    content = content.replace("{current_time}", current_time)
                    print(f"🔄 Replaced current_time with: {current_time}")

                placeholders = re.findall(r"{(.*?)}", content)
                for key in placeholders:
                    if key == "PlanStartDate":
                        value = current_time
                    elif key == "suffix":
                        value = str(suffix)
                    elif key in ["course_id", "CourseID", "COURSE_ID"]:
                        value = body.get("course_id") or "General"   # ✅ default
                    else:
                        value = str(body.get(key) or "")             # ✅ EMPTY if missing

                    content = content.replace(f"{{{key}}}", value)

                # 📝 Save final tfvars
                final_prefix = "final" if tfvars_prefix == "tfvars/" else "sds-final"
                final_key = f"{final_prefix}/terraform-{timestamp}-{suffix}-{template_base}.tfvars"
                s3.put_object(Bucket=BUCKET, Key=final_key, Body=content.encode())
                print(f"✅ Final tfvars saved to: {final_key}")

                # 🚀 Trigger CodeBuild
                print(f"🚀 Triggering CodeBuild: {project_name}")
                
                # ✅ MODIFIED: Use provided fields or defaults for normal user access
                env_vars = [
                    {'name': 'TFVARS_S3_KEY', 'value': final_key, 'type': 'PLAINTEXT'},
                    {'name': 'USER_EMAIL', 'value': body.get("usermail", "unknown"), 'type': 'PLAINTEXT'},
                    {'name': 'COURSE_ID', 'value': body.get("course_id", "splunk-test"), 'type': 'PLAINTEXT'},
                    {'name': 'TEMPLATE_FILE', 'value': template_name, 'type': 'PLAINTEXT'},
                    {'name': 'UNIQUE_ID', 'value': body.get("unique_id", ""), 'type': 'PLAINTEXT'},
                    {'name': 'START_DATE', 'value': body.get("start_date", ""), 'type': 'PLAINTEXT'},
                    {'name': 'ITEM_ID', 'value': body.get("id", ""), 'type': 'PLAINTEXT'}
                ]
                
                response = codebuild.start_build(
                    projectName=project_name,
                    environmentVariablesOverride=env_vars
                )

                actual_build_id = response["build"]["id"]

                triggered_projects.append({
                    'template': template_name,
                    'final_tfvars': final_key,
                    'codebuild_project': project_name,
                    'actual_build_id': actual_build_id
                })

                # ✅ Save to DynamoDB
                status_table.put_item(
                    Item={
                        "email_id": body.get("usermail"),
                        "build_id": actual_build_id,
                        "labs_type": f"{body.get('lab_category', 'aws-lab')}#{datetime.datetime.utcnow().isoformat()}",
                        "status": "in_progress",
                        "course_id":course_id,
                        "environment_name": project_name,
                        "lab_category" : body.get("lab_category"),
                        "instance_ids": [],
                        "created_at": datetime.datetime.utcnow().replace(microsecond=0).isoformat(),
                    }
                )
