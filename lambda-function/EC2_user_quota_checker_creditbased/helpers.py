from decimal import Decimal
from collections import defaultdict


def group_by_email(items):
    grouped = defaultdict(list)
    for item in items:
        grouped[item['email_id']].append(item)
    return grouped


def group_by_date(records):
    grouped = defaultdict(list)
    for r in records:
        date = r.get("date") or r.get("usage_date")
        grouped[date].append(r)
    return grouped


def build_html_table(records):
    rows = ""
    grand_total_credits = Decimal("0")

    for r in records:
        instance_name = r.get("instance_name", "N/A")
        compute_credits = r.get("compute_credits", Decimal("0"))
        storage_credits = r.get("storage_credits", Decimal("0"))
        total_credits = r.get("total_credits", Decimal("0"))

        grand_total_credits += total_credits

        rows += f"""
        <tr>
            <td>{instance_name}</td>
            <td align="right"> {compute_credits}</td>
            <td align="right"> {storage_credits}</td>
            <td align="right"><b> {total_credits}</b></td>
        </tr>
        """


    table = f"""
    <table border="1" cellpadding="8" cellspacing="0" width="100%" 
    style="border-collapse:collapse; font-family:Arial; font-size:14px;">
        <thead>
            <tr style="background-color:#f2f2f2;">
                <th align="left">Server Name</th>
                <th align="right">Running credits </th>
                <th align="right">Storage credits </th>
                <th align="right">Total credits </th>
            </tr>
        </thead>
        <tbody>
            {rows}
            <tr style="background-color:#fafafa; font-weight:bold;">
                <td align="left">Grand Total</td>
                <td></td>
                <td></td>
                <td align="right">₹ {grand_total_credits}</td>
            </tr>
        </tbody>
    </table>
    <br>
    """

    return table, grand_total_credits