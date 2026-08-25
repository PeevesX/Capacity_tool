"""
Shared capacity-planning logic for carding lines TRK0001 / TRK0002 (or more).
Both the CLI script and the Streamlit app import from here, so the math
only lives in one place.
"""

import pandas as pd

REQUIRED_ORDER_COLS = [
    "order_id", "product", "line", "month", "unit",
    "quantity", "width_m", "length_m", "cycle_time_sec_per_m",
]
REQUIRED_CALENDAR_COLS = ["line", "month", "working_days", "hours_per_day"]


def convert_to_meters(row: pd.Series) -> float:
    """Turn one order's quantity into linear meters, based on unit."""
    unit = row["unit"]

    if unit == "M":
        return row["quantity"]

    if unit == "M2":
        if pd.isna(row["width_m"]) or row["width_m"] == 0:
            raise ValueError(f"{row['order_id']}: M2 order needs width_m")
        return row["quantity"] / row["width_m"]

    if unit == "PCS":
        if pd.isna(row["length_m"]) or row["length_m"] == 0:
            raise ValueError(f"{row['order_id']}: PCS order needs length_m")
        return row["quantity"] * row["length_m"]

    raise ValueError(f"{row['order_id']}: unknown unit '{unit}'")


def compute_required_hours(row: pd.Series, oee_by_line: dict) -> float:
    """Ideal time for the meters, inflated by that line's OEE."""
    line = row["line"]
    if line not in oee_by_line:
        raise ValueError(f"{row['order_id']}: no OEE set for line '{line}'")
    ideal_hours = (row["meters"] * row["cycle_time_sec_per_m"]) / 3600
    return ideal_hours / oee_by_line[line]


def process_orders(orders: pd.DataFrame, oee_by_line: dict) -> pd.DataFrame:
    """Add meters + required_hours columns to a raw orders dataframe."""
    orders = orders.copy()
    orders["meters"] = orders.apply(convert_to_meters, axis=1)
    orders["required_hours"] = orders.apply(
        lambda r: compute_required_hours(r, oee_by_line), axis=1
    )
    return orders


def build_monthly_summary(orders: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    """One row per (line, month): capacity vs. required hours vs. utilization %."""
    calendar = calendar.copy()
    calendar["capacity_hours"] = calendar["working_days"] * calendar["hours_per_day"]

    demand = (
        orders.groupby(["line", "month"])["required_hours"]
        .sum()
        .reset_index()
    )
    summary = calendar.merge(demand, on=["line", "month"], how="left")
    summary["required_hours"] = summary["required_hours"].fillna(0)
    summary["utilization_pct"] = (
        summary["required_hours"] / summary["capacity_hours"] * 100
    )
    return summary.sort_values(["line", "month"]).reset_index(drop=True)


def validate_columns(df: pd.DataFrame, required: list, label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}")
