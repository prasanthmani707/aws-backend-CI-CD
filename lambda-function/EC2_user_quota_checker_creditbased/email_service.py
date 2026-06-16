import boto3
import logging
from helpers import build_html_table

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ses = boto3.client('ses')


def send_email(email, content, label, is_weekly=False):

    try:
        # ===== DAILY =====
        if not is_weekly:
            table_html, grand_total = build_html_table(content)

            html_content = f"""
            {table_html}
            <p><b>Grand Total:</b>  {grand_total}</p>
            """

            text_content = f"Grand Total:  {grand_total}"

        # ===== WEEKLY =====
        else:
            html_content = content
            text_content = "Weekly report included in HTML"

        html_body = f"""
        <html>
        <body style="font-family:Arial, sans-serif;">
            <p>Hello,</p>
            <p>Your <b>{label}</b> usage summary:</p>

            {html_content}

            <p>Thank you,<br>SoftMania Team</p>
        </body>
        </html>
        """

        text_body = f"""
Hello,

Your {label} usage summary.

{text_content}

Thank you,
SoftMania Team
"""

        ses.send_email(
            Source='eng-team@softmania.in',
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': f'Usage Report - {label}'},
                'Body': {
                    'Html': {'Data': html_body},
                    'Text': {'Data': text_body}
                }
            },
        )

        logger.info(f"Email sent to {email}")

    except Exception as e:
        logger.error(f"Email failed for {email}: {e}")