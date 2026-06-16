import math
from datetime import datetime, timedelta, timezone
from fetch_per_hour_gp_credits import fetch_per_hour_gp_credits

STORAGE_CREDITS_PER_GB_PER_HOUR = float(fetch_per_hour_gp_credits())

print(f"STORAGE_CREDITS_PER_GB_PER_HOUR {STORAGE_CREDITS_PER_GB_PER_HOUR}")

def calculate_expiry(stopped_instances, current_credits):

    # Total storage
    total_storage_gb = sum(
        float(inst.get('total_storage', 0) or 0)
        for inst in stopped_instances
    )

    print("Total Storage (GB):", total_storage_gb)

    if total_storage_gb <= 0:
        return None

    # Credits consumed per hour
    credits_per_hour = total_storage_gb * STORAGE_CREDITS_PER_GB_PER_HOUR

    if credits_per_hour == 0:
        return None

    # Total survival hours
    total_hours = current_credits / credits_per_hour

    # Remaining days
    # Total seconds
    total_seconds = int(total_hours * 3600)

    # Days
    days = total_seconds // 86400
    remaining_seconds = total_seconds % 86400

    # Hours
    hours = remaining_seconds // 3600
    remaining_seconds %= 3600

    # Minutes
    minutes = remaining_seconds // 60

    # Seconds
    seconds = remaining_seconds % 60

    formatted_days_remaining = f"{days} days {hours} hours"

    # UTC timezone-aware datetime
    now = datetime.now(timezone.utc)

    expiry_date = now + timedelta(hours=max(total_hours, 0))

    return {
        "total_storage_gb": total_storage_gb,
        "credits_per_hour": credits_per_hour,
        "total_hours": total_hours,
        "formatted_days_remaining": formatted_days_remaining,
        "expiry_date": expiry_date
    }