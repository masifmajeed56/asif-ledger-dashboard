import streamlit as st
import pandas as pd
import json
import re
import io
from datetime import datetime
from google.cloud import firestore

# Page Setup
st.set_page_config(page_title="Asif Ledger Solutions - Financial Dashboard", layout="wide")

# Database Connection
@st.cache_resource
def get_db():
    key_path = r"C:\projects\serviceAccountKey.json"
    return firestore.Client.from_service_account_json(key_path)

db = get_db()

# Chart of Accounts Category Mapper
CATEGORIES = {
    "Fuel & Automobile": ["shell", "pso", "total", "petrol", "fuel", "cng"],
    "Utilities": ["k-electric", "lesco", "fesco", "ptcl", "stormfiber", "sngpl", "bill"],
    "Groceries & Food": ["metro", "carrefour", "chaseup", "kfc", "mcdonalds", "foodpanda"],
    "Software & Services": ["google", "netflix", "openai", "aws", "github"],
    "Bank & Transfer Fees": ["fee", "tax", "charge", "atm fee"]
}

def auto_assign_category(merchant_name, sms_text):
    text = (merchant_name + " " + sms_text).lower()
    for category, keywords in CATEGORIES.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "General Expense"

def parse_sms_logic(sms_text):
    amount_match = re.search(r'(?:Rs\.?|INR|PKR|\$)\s*([\d,]+(?:\.\d{1,2})?)', sms_text, re.IGNORECASE)
    amount = float(amount_match.group(1).replace(',', '')) if amount_match else 0.0

    merchant_match = re.search(r'(?:to|at|paid to|sent to)\s+([A-Za-z0-9\s&]+?)(?=\s+(?:via|on|from|ref|dated|code|\.|$))', sms_text, re.IGNORECASE)
    merchant = merchant_match.group(1).strip() if merchant_match else "General Merchant"

    method_match = re.search(r'(?:via|using|through)\s+([A-Za-z0-9\s]+?)(?=\s+(?:on|dated|ref|\.|$))', sms_text, re.IGNORECASE)
    payment_method = method_match.group(1).strip() if method_match else "Direct Transfer"

    is_debit = any(word in sms_text.lower() for word in ["paid", "sent", "debited", "spent", "withdrawn"])
    cat = auto_assign_category(merchant, sms_text) if is_debit else "Income"

    return {
        "raw_sms": sms_text,
        "amount": amount,
        "merchant": merchant,
        "payment_method": payment_method,
        "type": "Debit" if is_debit else "Credit",
        "category": cat,
        "status": "processed",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# Header
st.title("💼 Asif Ledger Solutions - Financial Dashboard")
st.caption("Real-Time SMS Transaction Parser & Cloud Accounting")

# Sidebar - Live Input Form
st.sidebar.header("📩 Add Live SMS Transaction")
user_sms = st.sidebar.text_area("Paste SMS Text Here:", placeholder="Paid Rs 1,500 to Foodpanda via EasyPaisa.")

if st.sidebar.button("Process & Save Transaction"):
    if user_sms.strip():
        parsed_record = parse_sms_logic(user_sms)
        db.collection('transactions').add(parsed_record)
        st.sidebar.success("✅ Transaction Parsed & Saved!")
        st.rerun()
    else:
        st.sidebar.warning("Please enter an SMS first.")

# Fetch Data (FIXED TIMEZONE & MIXED INPUT CONVERSION)
def load_data():
    docs = db.collection('transactions').stream()
    data = []
    for doc in docs:
        d = doc.to_dict()
        if "timestamp" not in d or not d["timestamp"]:
            d["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data.append(d)
    if data:
        df_loaded = pd.DataFrame(data)
        # Convert all timestamps to UTC first to normalize mixed timezones
        df_loaded['timestamp'] = pd.to_datetime(df_loaded['timestamp'], errors='coerce', utc=True)
        # Convert timezone-naive datetime for clean display & date picking
        df_loaded['timestamp'] = df_loaded['timestamp'].dt.tz_localize(None)
        df_loaded['timestamp'] = df_loaded['timestamp'].fillna(pd.Timestamp.now())
        return df_loaded
    return pd.DataFrame()

df = load_data()

if not df.empty:
    # ------------------ SIDEBAR FILTERS ------------------
    st.sidebar.divider()
    st.sidebar.header("🔍 Filters & Date Range")

    # Category Filter
    all_categories = ["All"] + list(df['category'].dropna().unique())
    selected_category = st.sidebar.selectbox("Filter by Category:", all_categories)

    # Type Filter
    selected_type = st.sidebar.radio("Transaction Type:", ["All", "Debit (Expense)", "Credit (Income)"])

    # Date Range Selection
    min_date = df['timestamp'].min().date()
    max_date = df['timestamp'].max().date()

    date_range = st.sidebar.date_input(
        "Select Date Range:",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # Apply Filters
    filtered_df = df.copy()

    # Filter by Date
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df['timestamp'].dt.date >= start_date) & 
            (filtered_df['timestamp'].dt.date <= end_date)
        ]

    # Filter by Category
    if selected_category != "All":
        filtered_df = filtered_df[filtered_df['category'] == selected_category]

    # Filter by Type
    if selected_type == "Debit (Expense)":
        filtered_df = filtered_df[filtered_df['type'] == 'Debit']
    elif selected_type == "Credit (Income)":
        filtered_df = filtered_df[filtered_df['type'] == 'Credit']

    # ------------------ METRICS DISPLAY ------------------
    total_income = filtered_df[filtered_df['type'] == 'Credit']['amount'].sum()
    total_expense = filtered_df[filtered_df['type'] == 'Debit']['amount'].sum()
    net_balance = total_income - total_expense

    c1, c2, c3 = st.columns(3)
    c1.metric("Selected Income", f"Rs. {total_income:,.2f}")
    c2.metric("Selected Expenses", f"Rs. {total_expense:,.2f}")
    c3.metric("Net Balance", f"Rs. {net_balance:,.2f}")

    st.divider()

    # ------------------ VISUAL CHARTS ------------------
    if not filtered_df.empty:
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.subheader("Expenses by Category")
            expense_df = filtered_df[filtered_df['type'] == 'Debit']
            if not expense_df.empty:
                st.bar_chart(expense_df.groupby('category')['amount'].sum())
            else:
                st.info("No Expense Data in selected filter.")

        with col_chart2:
            st.subheader("Income vs Expense Ratio")
            st.bar_chart(filtered_df.groupby('type')['amount'].sum())
    else:
        st.warning("No data found for the selected filters.")

    st.divider()

    # ------------------ TABLE & EXPORT ------------------
    col_table, col_export = st.columns([3, 1])
    
    with col_table:
        st.subheader("📋 Filtered Transactions Table")
    
    def convert_df_to_csv(dataframe):
        return dataframe.to_csv(index=False).encode('utf-8')

    def convert_df_to_excel(dataframe):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            dataframe.to_excel(writer, index=False, sheet_name='Filtered Transactions')
        return output.getvalue()

    with col_export:
        st.subheader("📥 Export Filtered")
        if not filtered_df.empty:
            csv_data = convert_df_to_csv(filtered_df)
            st.download_button(
                label="📄 Export CSV",
                data=csv_data,
                file_name="filtered_transactions.csv",
                mime="text/csv"
            )
            
            excel_data = convert_df_to_excel(filtered_df)
            st.download_button(
                label="📊 Export Excel",
                data=excel_data,
                file_name="filtered_transactions.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    if not filtered_df.empty:
        display_df = filtered_df.copy()
        display_df['Date & Time'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(
            display_df[['Date & Time', 'amount', 'merchant', 'category', 'type', 'payment_method', 'status']],
            width='stretch'
        )

else:
    st.info("No transactions found. Use the sidebar to paste and add your first SMS!")