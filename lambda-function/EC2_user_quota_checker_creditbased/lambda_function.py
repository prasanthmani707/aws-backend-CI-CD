import json
from datetime import datetime, timedelta
import logging

from dynamodb_ops import query_by_date
from helpers import group_by_email, group_by_date, build_html_table
from email_service import send_email

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    today = datetime.utcnow().date()
    today_str = today.isoformat()

    # ================= DAILY =================
    daily_items = query_by_date(today_str)

    if daily_items:
        daily_grouped = group_by_email(daily_items)

        for email, records in daily_grouped.items():
            send_email(email, records, f"Daily ({today_str})")
    else:
        logger.info("No daily data found")

    # ================= WEEKLY =================
    weekly_items = []

    for i in range(7):
        day_str = (today - timedelta(days=i)).isoformat()
        items = query_by_date(day_str)
        if items:  # avoid extending empty lists
            weekly_items.extend(items)

    if not weekly_items:
        logger.info("No weekly data found")
        return {
            "statusCode": 200,
            "body": json.dumps("Processed successfully (no weekly data)")
        }

    weekly_grouped = group_by_email(weekly_items)

    for email, records in weekly_grouped.items():

        date_grouped = group_by_date(records)

        html_parts = []   # ✅ O(n) instead of O(n²)
        weekly_total = 0

        # 👉 Sort once
        sorted_dates = sorted(date_grouped.keys(), reverse=True)

        for date in sorted_dates:
            day_records = date_grouped[date]

            table_html, day_total = build_html_table(day_records)
            weekly_total += float(day_total)

            html_parts.append(f"""
            <details style="margin-top:12px;">
                <summary style="
                    cursor:pointer;
                    font-weight:bold;
                    font-size:15px;
                    padding:6px;
                    background-color:#f5f5f5;
                    border:1px solid #ddd;
                ">
                     {date} —  {day_total}
                </summary>

                <div style="margin-top:10px;">
                    {table_html}
                </div>
            </details>
            """)

        # 👉 Weekly total
        html_parts.append(f"""
        <div style="margin-top:20px; font-size:16px; font-weight:bold;">
            Weekly Grand Total:  {round(weekly_total, 2)}
        </div>
        """)

        weekly_html = "".join(html_parts)  # ✅ efficient

        label = f"Weekly ({(today - timedelta(days=6)).isoformat()} to {today_str})"

        send_email(email, weekly_html, label, is_weekly=True)

    return {
        "statusCode": 200,
        "body": json.dumps("Daily and weekly emails processed successfully")
    }