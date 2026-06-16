import boto3
import json
# big of O
# ==========================================================
# TIME COMPLEXITY ANALYSIS
# ==========================================================
# Step 1: Check CommunityMembers table  -> O(1) 
# Step 2: Check CreditBased table       -> O(1)
# Step 3: Invoke another Lambda         -> O(1)
#
# Total Time Complexity:
# T(n) = O(1) + O(1) + O(1)
#      = O(3)
#      = O(1)
#
# SPACE COMPLEXITY:
# O(1)
# ==========================================================


# ---------------- AWS RESOURCES ----------------
dynamodb_us_west = boto3.resource("dynamodb", region_name="us-west-2")
dynamodb_us_east = boto3.resource("dynamodb", region_name="us-east-1")

community_member = dynamodb_us_west.Table("CommunityMembers")
creditbased_member = dynamodb_us_east.Table("user_profile_creditbased")

lambda_client = boto3.client("lambda", region_name="us-west-2")


def check_user(email_id):
    try:
        print(f"[INFO] Checking user: {email_id}")

        # ---------------- Normalize email ----------------
        email_id = email_id.strip().lower()

        # ======================================================
        # STEP 1: CommunityMembers
        # ======================================================
        print("[STEP 1] Checking CommunityMembers...")
        res1 = community_member.get_item(Key={"email": email_id})
        com_user = res1.get("Item")

        if com_user:
            print("[FOUND] CommunityMembers")
            return {
                "status": "found",
                "source": "community_member",
                "data": com_user
            }

        # ======================================================
        # STEP 2: CreditBased
        # ======================================================
        print("[STEP 2] Checking CreditBased...")
        res2 = creditbased_member.get_item(Key={"email_id": email_id})
        print(f"user email is present{res2}")
        credit_user = res2.get("Item")
        print(f"credit user {credit_user}")

        if credit_user:
            print("[FOUND] CreditBased")
            return {
                "status": "found",
                "source": "creditbased_user",
                "data": credit_user
            }

        # ======================================================
        # STEP 3: TrainerCentral Lambda
        # ======================================================
        # print("[STEP 3] Invoking TrainerCentral Lambda")

        # res3 = lambda_client.invoke(
        #     FunctionName="check_trainercentral_user",
        #     InvocationType="RequestResponse",
        #     Payload=json.dumps({
        #         "queryStringParameters": {
        #             "email": email_id
        #         }
        #     })
        # )

        # raw_payload = res3["Payload"].read().decode("utf-8")
        # lambda_result = json.loads(raw_payload)

        # print("[LAMBDA RAW RESPONSE]", lambda_result)

        # ======================================================
        # SAFE BODY PARSING
        # ======================================================
        # body = lambda_result.get("body")

        # if isinstance(body, str):
        #     body = json.loads(body)

        # print("[PARSED BODY]", body)

        # ======================================================
        # EMAIL FIELD NORMALIZATION (VERY IMPORTANT FIX)
        # ======================================================
        # user_email = (
        #     body.get("email")
        #     or body.get("Email")
        #     or body.get("emailId")
        # )

        # if user_email and user_email.strip().lower() == email_id:
        #     print("[FOUND] TrainerCentral")
        #     return {
        #         "status": "found",
        #         "source": "trainercentral_user",
        #         "data": body
        #     }

        # NOT FOUND
        return False

    except Exception as e:
        print("[ERROR]", str(e))
        return {
            "status": "error",
            "message": str(e)
        }