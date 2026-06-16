import json
import boto3
import os
from botocore.exceptions import ClientError

# Auto-fetch AWS region dynamically
try:
    session = boto3.session.Session()
    REGION = session.region_name or os.getenv("AWS_REGION")
except Exception:
    REGION = os.getenv("AWS_REGION")

ec2 = boto3.client('ec2', region_name=REGION)

def lambda_handler(event, context):
    try:
        # Handle both API Gateway and direct Lambda invocation
        query_params = event.get("queryStringParameters") or {}
        body = json.loads(event.get("body", "{}")) if event.get("body") else {}
        data = {**body, **query_params}

        # Robust HTTP method detection
        http_method = (
            event.get("httpMethod") or 
            event.get("requestContext", {}).get("http", {}).get("method") or
            event.get("method")
        )
        if http_method:
            http_method = http_method.upper()
        else:
            return response(400, {"error": "HTTP method not detected"})

        if http_method == "GET":
            return get_security_groups(data)
        elif http_method == "POST":
            return add_security_group_rule(data)
        elif http_method == "DELETE":
            return delete_security_group_rule(data)
        elif http_method == "PUT":
            return update_security_group_rule(data)
        else:
            return response(400, {"error": "Invalid HTTP method. Use GET, POST, PUT, or DELETE."})

    except Exception as e:
        return response(500, {"error": str(e)})


# -------------------------------
# Helper response function
# -------------------------------
def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, indent=2)
    }


# -------------------------------
# Get Security Groups
# -------------------------------
def get_security_groups(data):
    instance_id = data.get("instance_id")
    sg_id = data.get("sg_id")
    direction = data.get("direction", "all").lower()

    if not instance_id and not sg_id:
        return response(400, {"error": "Provide instance_id or sg_id"})

    try:
        sg_ids = []
        if instance_id:
            instance_info = ec2.describe_instances(InstanceIds=[instance_id])
            sg_ids = [sg['GroupId'] for res in instance_info['Reservations']
                      for inst in res['Instances']
                      for sg in inst['SecurityGroups']]
        elif sg_id:
            sg_ids = [sg_id]

        sg_list = []
        for sg in sg_ids:
            sg_details = ec2.describe_security_group_rules(Filters=[{"Name": "group-id", "Values": [sg]}])
            inbound_rules, outbound_rules = [], []

            for rule in sg_details.get("SecurityGroupRules", []):
                rule_data = {
                    "SecurityGroupRuleId": rule.get("SecurityGroupRuleId"),
                    "Protocol": rule.get("IpProtocol") or "-1",
                    "FromPort": rule.get("FromPort", "-1"),
                    "ToPort": rule.get("ToPort", "-1"),
                    "CidrIp": rule.get("CidrIpv4", "N/A"),
                    "IsEgress": rule.get("IsEgress")
                }
                if rule.get("IsEgress"):
                    outbound_rules.append(rule_data)
                else:
                    inbound_rules.append(rule_data)

            entry = {"GroupId": sg}
            if direction in ["inbound", "all"]:
                entry["InboundRules"] = inbound_rules
            if direction in ["outbound", "all"]:
                entry["OutboundRules"] = outbound_rules

            sg_list.append(entry)

        return response(200, {"SecurityGroups": sg_list})

    except ClientError as e:
        return response(500, {"error": str(e)})


# -------------------------------
# Add Security Group Rule
# -------------------------------
def add_security_group_rule(data):
    sg_id, instance_id = data.get("sg_id"), data.get("instance_id")
    direction = data.get("direction", "inbound").lower()
    protocol = data.get("protocol", "tcp")
    from_port = data.get("from_port")
    to_port = data.get("to_port", from_port)
    cidr_ip = data.get("cidr_ip", "0.0.0.0/0")

    if from_port is None:
        return response(400, {"error": "from_port is required"})
    try:
        from_port = int(from_port)
        to_port = int(to_port) if to_port is not None else from_port
    except (TypeError, ValueError):
        return response(400, {"error": "from_port and to_port must be valid integers"})

    # Auto-fetch sg_id if not provided
    if not sg_id and instance_id:
        instance_info = ec2.describe_instances(InstanceIds=[instance_id])
        sg_id = [sg['GroupId'] for res in instance_info['Reservations']
                 for inst in res['Instances']
                 for sg in inst['SecurityGroups']][0]

    ip_permission = {
        'IpProtocol': protocol,
        'FromPort': from_port,
        'ToPort': to_port,
        'IpRanges': [{'CidrIp': cidr_ip}]
    }

    try:
        if direction == "inbound":
            ec2.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=[ip_permission])
        else:
            ec2.authorize_security_group_egress(GroupId=sg_id, IpPermissions=[ip_permission])
        return response(200, {"message": f"Rule added successfully to {sg_id}"})
    except ClientError as e:
        return response(500, {"error": str(e)})


# -------------------------------
# Delete Security Group Rule
# -------------------------------
def delete_security_group_rule(data):
    sg_id, instance_id = data.get("sg_id"), data.get("instance_id")
    direction = data.get("direction", "inbound").lower()
    protocol = data.get("protocol", "tcp")
    from_port = data.get("from_port")
    to_port = data.get("to_port", from_port)
    cidr_ip = data.get("cidr_ip", "0.0.0.0/0")

    if from_port is None:
        return response(400, {"error": "from_port is required"})
    try:
        from_port = int(from_port)
        to_port = int(to_port) if to_port is not None else from_port
    except (TypeError, ValueError):
        return response(400, {"error": "from_port and to_port must be valid integers"})

    # Auto-fetch sg_id if not provided
    if not sg_id and instance_id:
        instance_info = ec2.describe_instances(InstanceIds=[instance_id])
        sg_id = [sg['GroupId'] for res in instance_info['Reservations']
                 for inst in res['Instances']
                 for sg in inst['SecurityGroups']][0]

    ip_permission = {
        "IpProtocol": protocol,
        "FromPort": from_port,
        "ToPort": to_port,
        "IpRanges": [{"CidrIp": cidr_ip}]
    }

    try:
        if direction == "inbound":
            ec2.revoke_security_group_ingress(GroupId=sg_id, IpPermissions=[ip_permission])
        else:
            ec2.revoke_security_group_egress(GroupId=sg_id, IpPermissions=[ip_permission])
        return response(200, {"message": f"Rule deleted successfully from {sg_id}"})
    except ClientError as e:
        return response(500, {"error": str(e)})


# -------------------------------
# Update Security Group Rule
# -------------------------------
def update_security_group_rule(data):
    try:
        # Delete old rule first
        delete_data = {
            "sg_id": data.get("sg_id"),
            "instance_id": data.get("instance_id"),
            "direction": data.get("direction"),
            "protocol": data.get("old_protocol"),
            "from_port": data.get("old_from_port"),
            "to_port": data.get("old_to_port"),
            "cidr_ip": data.get("old_cidr_ip")
        }
        delete_resp = delete_security_group_rule(delete_data)
        if delete_resp["statusCode"] != 200:
            return delete_resp

        # Add new rule
        add_data = {
            "sg_id": data.get("sg_id"),
            "instance_id": data.get("instance_id"),
            "direction": data.get("direction"),
            "protocol": data.get("new_protocol"),
            "from_port": data.get("new_from_port"),
            "to_port": data.get("new_to_port"),
            "cidr_ip": data.get("new_cidr_ip")
        }
        add_resp = add_security_group_rule(add_data)

        # Use the actual SG ID returned from add_security_group_rule
        if add_resp["statusCode"] == 200:
            # Extract SG ID from the add response message
            original_msg = add_resp["body"]
            try:
                body_json = json.loads(original_msg)
                sg_id_used = body_json.get("message", "").split()[-1]  # last word = sg_id
            except:
                sg_id_used = data.get("sg_id", "Unknown")
            return response(200, {"message": f"Rule updated successfully to {sg_id_used}"})

        return add_resp

    except Exception as e:
        return response(500, {"error": str(e)})

    try:
        # Delete old rule first
        delete_data = {
            "sg_id": data.get("sg_id"),
            "instance_id": data.get("instance_id"),
            "direction": data.get("direction"),
            "protocol": data.get("old_protocol"),
            "from_port": data.get("old_from_port"),
            "to_port": data.get("old_to_port"),
            "cidr_ip": data.get("old_cidr_ip")
        }
        delete_resp = delete_security_group_rule(delete_data)
        if delete_resp["statusCode"] != 200:
            return delete_resp

        # Add new rule
        add_data = {
            "sg_id": data.get("sg_id"),
            "instance_id": data.get("instance_id"),
            "direction": data.get("direction"),
            "protocol": data.get("new_protocol"),
            "from_port": data.get("new_from_port"),
            "to_port": data.get("new_to_port"),
            "cidr_ip": data.get("new_cidr_ip")
        }
        return add_security_group_rule(add_data)

    except Exception as e:
        return response(500, {"error": str(e)})
