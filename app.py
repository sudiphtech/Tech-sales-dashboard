from datetime import date
from io import BytesIO
from pathlib import Path
import zipfile

import altair as alt
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Tech products sales",
    page_icon=":material/monitoring:",
    layout="wide",
)

DATA_PATH = Path(__file__).parent / "data" / "Tech_Products_Sales_Data.xlsx"
REQUIRED_COLUMNS = [
    "Transaction ID",
    "Product",
    "Quantity",
    "Unit Price (INR)",
    "Date",
    "Customer Name",
    "State",
    "Country",
    "Sales Channel",
    "Payment Type",
    "Sales",
]
NUMERIC_COLUMNS = ["Quantity", "Unit Price (INR)", "Sales"]
CURRENCY_FORMAT = "₹%.2f"


@st.cache_data(show_spinner="Loading sales data...")
def load_sales_data(contents: bytes) -> pd.DataFrame:
    """Read and validate the uploaded Excel workbook."""
    data = pd.read_excel(BytesIO(contents), sheet_name=0)
    data.columns = data.columns.astype(str).str.strip()

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
    if data.empty:
        raise ValueError("The selected worksheet does not contain any sales records.")

    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    if data["Date"].isna().any():
        invalid_count = int(data["Date"].isna().sum())
        raise ValueError(f"{invalid_count:,} sales record(s) have a blank or invalid date.")

    for column in NUMERIC_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")
        if data[column].isna().any():
            invalid_count = int(data[column].isna().sum())
            raise ValueError(
                f"{invalid_count:,} sales record(s) have a blank or invalid "
                f"value in '{column}'."
            )

    return data


def filter_data(
    data: pd.DataFrame,
    date_range: tuple[date, date],
    selections: dict[str, list[str]],
) -> pd.DataFrame:
    """Apply the dashboard's date and category filters."""
    start_date, end_date = date_range
    filtered = data.loc[data["Date"].dt.date.between(start_date, end_date)]

    for column, selected in selections.items():
        if selected:
            filtered = filtered.loc[filtered[column].astype(str).isin(selected)]

    return filtered


def format_inr(value: float) -> str:
    return f"₹{value:,.2f}"


def style_chart(chart):
    return (
        chart.configure_view(stroke=None)
        .configure_axis(gridColor="#293548", labelColor="#AAB8CC", titleColor="#AAB8CC")
    )


uploaded_file = None
with st.sidebar:
    st.title("Sales dashboard")
    st.caption("Explore product performance and customer orders.")
    uploaded_file = st.file_uploader(
        "Upload a sales workbook",
        type=["xlsx"],
        help="Upload an Excel workbook with a sales data worksheet.",
    )

    if uploaded_file is None:
        if not DATA_PATH.is_file():
            st.error(
                "The default workbook is missing. Upload the sales Excel workbook to continue."
            )
            st.stop()
        workbook_bytes = DATA_PATH.read_bytes()
        st.caption(f"Using `{DATA_PATH.name}`")
    else:
        workbook_bytes = uploaded_file.getvalue()
        st.caption(f"Using `{uploaded_file.name}`")

try:
    sales = load_sales_data(workbook_bytes)
except (OSError, ValueError, ImportError, zipfile.BadZipFile) as error:
    st.error(f"Could not load the sales workbook: {error}")
    st.stop()

with st.sidebar:
    min_date = sales["Date"].min().date()
    max_date = sales["Date"].max().date()
    chosen_dates = st.date_input(
        "Order date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    selections: dict[str, list[str]] = {}
    for column, label in [
        ("Product", "Products"),
        ("Country", "Countries"),
        ("State", "States"),
        ("Sales Channel", "Sales channels"),
        ("Payment Type", "Payment types"),
    ]:
        options = sorted(sales[column].dropna().astype(str).unique().tolist())
        selections[column] = st.multiselect(
            label,
            options,
            placeholder="All",
            key=f"filter_{column}",
        )

    st.download_button(
        "Download filtered data",
        data=sales.to_csv(index=False).encode("utf-8-sig"),
        file_name="filtered_sales.csv",
        mime="text/csv",
        width="stretch",
    )

st.title("Tech products sales")
st.caption("Sales performance, order trends, and customer insights")

if not isinstance(chosen_dates, (tuple, list)) or len(chosen_dates) != 2:
    st.info("Select a start and end date to view the dashboard.")
    st.stop()

filtered_sales = filter_data(sales, tuple(chosen_dates), selections)
if filtered_sales.empty:
    st.warning("No sales records match the selected filters.")
    st.stop()

total_sales = float(filtered_sales["Sales"].sum())
total_orders = int(filtered_sales["Transaction ID"].nunique())
total_quantity = int(filtered_sales["Quantity"].sum())
total_customers = int(filtered_sales["Customer Name"].nunique())
average_order_value = total_sales / total_orders if total_orders else 0.0

with st.container(horizontal=True):
    st.metric("Total sales", format_inr(total_sales), border=True)
    st.metric("Orders", f"{total_orders:,}", border=True)
    st.metric("Units sold", f"{total_quantity:,}", border=True)
    st.metric("Customers", f"{total_customers:,}", border=True)
    st.metric("Average order value", format_inr(average_order_value), border=True)

overview_tab, customers_tab, transactions_tab = st.tabs(
    ["Overview", "Customers", "Transactions"]
)

with overview_tab:
    monthly_sales = (
        filtered_sales.assign(Month=filtered_sales["Date"].dt.to_period("M").dt.to_timestamp())
        .groupby("Month", as_index=False)["Sales"]
        .sum()
    )
    products = (
        filtered_sales.groupby("Product", as_index=False)["Sales"]
        .sum()
        .nlargest(10, "Sales")
        .sort_values("Sales")
    )
    channels = (
        filtered_sales.groupby("Sales Channel", as_index=False)["Sales"]
        .sum()
        .sort_values("Sales", ascending=False)
    )
    payments = (
        filtered_sales.groupby("Payment Type", as_index=False)["Sales"]
        .sum()
        .nlargest(8, "Sales")
        .sort_values("Sales")
    )
    states = (
        filtered_sales.groupby("State", as_index=False)["Sales"]
        .sum()
        .nlargest(10, "Sales")
        .sort_values("Sales")
    )

    with st.container(border=True):
        st.subheader("Monthly sales")
        monthly_base = alt.Chart(monthly_sales).encode(
            x=alt.X("Month:T", title=None, axis=alt.Axis(format="%b %Y", labelAngle=0)),
            y=alt.Y("Sales:Q", title="Sales (INR)", axis=alt.Axis(format="~s")),
            tooltip=[
                alt.Tooltip("Month:T", title="Month", format="%B %Y"),
                alt.Tooltip("Sales:Q", title="Sales", format=",.2f"),
            ],
        )
        monthly_chart = (
            monthly_base.mark_area(color="#60A5FA", opacity=0.18)
            + monthly_base.mark_line(color="#60A5FA", point=True, strokeWidth=2)
        ).properties(height=280)
        st.altair_chart(style_chart(monthly_chart), width="stretch")

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Sales by product")
            product_chart = (
                alt.Chart(products)
                .mark_bar(color="#60A5FA", cornerRadiusEnd=4)
                .encode(
                    x=alt.X("Sales:Q", title="Sales (INR)", axis=alt.Axis(format="~s")),
                    y=alt.Y("Product:N", sort="-x", title=None),
                    tooltip=[
                        alt.Tooltip("Product:N", title="Product"),
                        alt.Tooltip("Sales:Q", title="Sales", format=",.2f"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(style_chart(product_chart), width="stretch")

    with right:
        with st.container(border=True):
            st.subheader("Sales by channel")
            channel_chart = (
                alt.Chart(channels)
                .mark_arc(innerRadius=65, outerRadius=110)
                .encode(
                    theta=alt.Theta("Sales:Q", title="Sales"),
                    color=alt.Color("Sales Channel:N", title="Channel"),
                    tooltip=[
                        alt.Tooltip("Sales Channel:N", title="Channel"),
                        alt.Tooltip("Sales:Q", title="Sales", format=",.2f"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(style_chart(channel_chart), width="stretch")

    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            st.subheader("Sales by payment type")
            payment_chart = (
                alt.Chart(payments)
                .mark_bar(color="#34D399", cornerRadiusEnd=4)
                .encode(
                    x=alt.X("Sales:Q", title="Sales (INR)", axis=alt.Axis(format="~s")),
                    y=alt.Y("Payment Type:N", sort="-x", title=None),
                    tooltip=[
                        alt.Tooltip("Payment Type:N", title="Payment type"),
                        alt.Tooltip("Sales:Q", title="Sales", format=",.2f"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(style_chart(payment_chart), width="stretch")

    with right:
        with st.container(border=True):
            st.subheader("Top states by sales")
            state_chart = (
                alt.Chart(states)
                .mark_bar(color="#A78BFA", cornerRadiusEnd=4)
                .encode(
                    x=alt.X("Sales:Q", title="Sales (INR)", axis=alt.Axis(format="~s")),
                    y=alt.Y("State:N", sort="-x", title=None),
                    tooltip=[
                        alt.Tooltip("State:N", title="State"),
                        alt.Tooltip("Sales:Q", title="Sales", format=",.2f"),
                    ],
                )
                .properties(height=280)
            )
            st.altair_chart(style_chart(state_chart), width="stretch")

with customers_tab:
    customer_summary = (
        filtered_sales.groupby("Customer Name", as_index=False)
        .agg(
            Orders=("Transaction ID", "nunique"),
            Sales=("Sales", "sum"),
            **{"Units sold": ("Quantity", "sum")},
        )
        .sort_values("Sales", ascending=False)
    )
    st.subheader("Customer leaderboard")
    st.dataframe(
        customer_summary,
        column_config={
            "Sales": st.column_config.NumberColumn(format=CURRENCY_FORMAT),
            "Orders": st.column_config.NumberColumn(format="%d"),
            "Units sold": st.column_config.NumberColumn(format="%d"),
        },
        hide_index=True,
        height=520,
    )

with transactions_tab:
    st.subheader("Sales transactions")
    st.dataframe(
        filtered_sales.sort_values("Date", ascending=False),
        column_config={
            "Date": st.column_config.DateColumn(format="MMM DD, YYYY"),
            "Unit Price (INR)": st.column_config.NumberColumn(format=CURRENCY_FORMAT),
            "Sales": st.column_config.NumberColumn(format=CURRENCY_FORMAT),
            "Quantity": st.column_config.NumberColumn(format="%d"),
        },
        hide_index=True,
        height=600,
    )

st.caption(
    f"Showing {len(filtered_sales):,} of {len(sales):,} transactions "
    f"from {filtered_sales['Date'].min():%b %d, %Y} "
    f"to {filtered_sales['Date'].max():%b %d, %Y}."
)
