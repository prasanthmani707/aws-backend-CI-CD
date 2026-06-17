import boto3
import json

# Oregon Region
lambda_client = boto3.client(
    "lambda",
    region_name="us-west-2"
)


def create_showcase_community_member(name):
    """
    Create a member in CommunityMembersShowcase Lambda

    Args:
        name (str): Member name

    Returns:
        dict
    """
    try:
        payload = {
            "body": json.dumps({
                "action": "create",
                "member": {
                    "name": name
                }
            })
        }

        response = lambda_client.invoke(
            FunctionName="CommunityMembersShowcase",
            InvocationType="RequestResponse",
            Payload=json.dumps(payload)
        )

        result = json.loads(
            response["Payload"].read()
        )

        body = json.loads(
            result.get("body", "{}")
        )

        return {
            "success": body.get("success", False),
            "memberId": body.get("memberId"),
            "message": body.get("message")
        }

    except Exception as e:
        print(f"CommunityMembersShowcase Error: {str(e)}")

        return {
            "success": False,
            "memberId": None,
            "message": str(e)
        }