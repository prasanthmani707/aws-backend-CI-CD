import json
import re 
import boto3
import random
import datetime
import logging
dynamodb = boto3.resource("dynamodb")
status_table = dynamodb.Table("User_environment_history_creditbased")

from key_pairs import create_ec2_key_and_upload, check_s3_key_exists, check_ec2_key_exists
from user_account_check import user_account_check
from project_based_labs import handle_direct_triggers
from helper import get_splunk_version, build_versioned_prefix
from custom_based_lab import process_template_file
from Cooldown_Mechanism import Cooldown_Mechanism
from auth_utils import get_email_from_event

def lambda_handler(event, context):
    print("📩 Event received:", event)
    try:
        # ✅ Safe body parsing
        if "body" in event and isinstance(event["body"], str):
            body = json.loads(event["body"])
        elif "body" in event and isinstance(event["body"], dict):
            body = event["body"]
        else:
            body = event

        for k, v in list(body.items()):
            if v is None:
                body[k] = "null"

        template_files = body.get('template_file') or []
        if isinstance(template_files, str):
            template_files = template_files.strip()
            if template_files.startswith('[') and template_files.endswith(']'):
                try:
                    template_files = json.loads(template_files)
                except json.JSONDecodeError:
                    template_files = [template_files]
            else:
                template_files = [template_files]

        email_id, error = get_email_from_event(event)
        print(f"email id : {email_id}")

        if error:
            return error


        usermail = email_id.lower()
        # usermail = body.get("usermail").lower()
        course_id = body.get('course_id') or "General"
        start_date = body.get('start_date', '')  # Optional # 
        splunk_version = get_splunk_version(body)
        username = body.get('username')
        soar_install_raw = str(body.get("soar_install", "no")).strip().lower()
        soar_install = "yes" if soar_install_raw in ["yes", "true"] else "no"
        install_splunk = "yes" if str(body.get("splunk_install", "")).lower() in ["true", "yes"] else "no"
        botsv3 = "yes" if str(body.get("botsv3", "")).lower() in ["true", "yes"] else "no"
        key_name = body.get('key_name', username or 'default')
        lab_category = body.get('lab_category')

        created_at_time = Cooldown_Mechanism(usermail)


        if not created_at_time:
            return {
                # 429 is the rate limit status code 
                "statusCode": 429,
                "body": json.dumps({"error": "Please wait for 2 minutes before triggering again to avoid duplicate environment creation."}),
            }


        lowercase_keywords = ["mysql", "mssql", "ossec", "syslog", "jenkins", "linux", "openvpn", "windows"]
        processed_templates = []
        for f in template_files:
            if any(keyword in f.lower() for keyword in lowercase_keywords):
                processed_templates.append(f.lower())
            else:
                processed_templates.append(f)
        template_files = processed_templates

        if not template_files:
            print("❌ No template files provided")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing template_file(s)'})}
        if not username or not usermail:
            print("❌ Missing username or usermail in request")
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing username or usermail'})}

        if not user_account_check(usermail):
            print("❌ User account check failed")
            return {'statusCode': 400, 'body': json.dumps({'error': 'invalid user'})}
        if not check_s3_key_exists(usermail, key_name) and not check_ec2_key_exists(key_name):
            print(f"🔑 Key not found in S3 and EC2 for user {usermail}, creating new key...")
            key_name = create_ec2_key_and_upload(username, key_name)


        triggered_projects = []

        # ✅ Call direct triggers handler
        handle_direct_triggers(body, triggered_projects)
        
        for template_file in template_files:
            if any(d["template"] == template_file for d in triggered_projects):
                print(f"⏭️ Skipping tfvars generation for already triggered template: {template_file}")
                continue 
            try:
                result = process_template_file(
                    template_file=template_file,
                    body=body,
                    triggered_projects=triggered_projects,
                    splunk_version=splunk_version,
                    install_splunk=install_splunk,
                    botsv3=botsv3,
                    soar_install=soar_install,
                    usermail=usermail,
                    course_id=course_id,
                    unique_id=body.get("id", ""),
                    start_date=start_date,
                )
                if result:
                    triggered_projects.append(result)
    
            except ValueError as e:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": str(e)}),
                }
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f"{len(triggered_projects)} project(s) triggered",
                'details': triggered_projects
            })
        }

    except Exception as e:
        print("❌ Error occurred:", str(e))
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
