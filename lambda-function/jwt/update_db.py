import json
import boto3

lambda_client = boto3.client(
    "lambda",
    region_name="us-west-2"
)


def update_db(email_id, body):

    # -----------------------------
    # NAME SPLIT LOGIC
    # -----------------------------

    full_name = body.get("name", "").strip()
    print("name",full_name)

    name_parts = full_name.split()

    # Single word
    if len(name_parts) == 1:

        first_name = name_parts[0]

        last_name = name_parts[0]

    # Multiple words
    else:

        first_name = name_parts[0]

        last_name = "".join(name_parts[1:])

    # -----------------------------
    # DEBUG LOGS
    # -----------------------------

    print("FULL NAME :", full_name)

    print("FIRST NAME :", first_name)

    print("LAST NAME :", last_name)

    # -----------------------------
    # PAYLOAD
    # -----------------------------

    payload = {

        "rawPath": "/members/add",

        "requestContext": {
            "http": {
                "method": "POST"
            }
        },

        "body": json.dumps({

            "email": email_id,

            "first_name": first_name,

            "last_name": last_name,

            "phone_number": body.get(
                "phone",
                ""
            ),

            "address": f"{body.get('address', {}).get('street', '')}, "
           f"{body.get('address', {}).get('city', '')}, "
           f"{body.get('address', {}).get('state', '')}, "
           f"{body.get('address', {}).get('pincode', '')}, "
           f"{body.get('address', {}).get('country', '')}"

        })
    }

    print("FINAL PAYLOAD :", payload)

    # -----------------------------
    # LAMBDA INVOKE
    # -----------------------------

    response = lambda_client.invoke(

        FunctionName="user_community_subscription",

        InvocationType="RequestResponse",

        Payload=json.dumps(payload)
    )

    lambda_response = json.loads(

        response["Payload"]
        .read()
        .decode("utf-8")
    )

    return lambda_response