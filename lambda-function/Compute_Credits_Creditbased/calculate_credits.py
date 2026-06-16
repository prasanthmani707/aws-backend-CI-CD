from datetime import datetime
from decimal import Decimal

def calculate_credits(running_item, event_time):
    try:
        # Use last_calculated_time for incremental calculation
        last_time_str = running_item.get("last_calculated_time", running_item["start_time"])
        last_time = datetime.fromisoformat(last_time_str)

        total_seconds = int((event_time - last_time).total_seconds())
        if total_seconds <= 0:
            return Decimal("0"), 0

        hours_decimal = Decimal(str(total_seconds)) / Decimal("3600")
        per_hour_credits = Decimal(str(running_item["per_hour_credits"]))

        incremental_credits = (hours_decimal * per_hour_credits).quantize(Decimal("0.00001"))

        return incremental_credits, total_seconds

    except Exception as e:
        print(f"Error calculating credits: {e}")
        return Decimal("0"), 0