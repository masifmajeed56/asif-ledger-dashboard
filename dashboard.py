import streamlit as st
import pandas as pd
import json
import re
import io
import hashlib
from datetime import datetime
from google.cloud import firestore
from google.oauth2 import service_account

# Page Setup
st.set_page_config(page_title="AI Ledger - Multi-Tenant Business Engine", layout="wide")

# Database Connection (Supports Streamlit Cloud Secrets & Local C: Drive)
@st.cache_resource
def get_db():
    if "FIREBASE_KEY" in st.secrets:
        key_dict = json.loads(st.secrets["FIREBASE_KEY"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds, project=key_dict["project_id"])
    else:
        key_path = r"C:\projects\serviceAccountKey.json"
        return firestore.Client.from_service_account_json(key_path)

db = get_db()

# Password Hashing Function
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# ------------------ SESSION STATE INITIALIZATION ------------------
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = ""
if 'business_id' not in st.session_state:
    st.session_state['business_id'] = ""
if 'business_details' not in st.session_state:
    st.session_state['business_details'] = {}

# ------------------ SCREEN 1: LOGIN / SIGNUP / ONBOARDING ------------------
if not st.session_state['logged_in']:
    st.title("💼 AI Ledger Solutions")
    st.subheader("Multi-Business Cloud Accounting Platform")
    
    auth_mode = st.radio("Choose Action:", ["Login", "Sign Up (Create New Business Account)"], horizontal=True)
    st.divider()

    col_auth, _ = st.columns([2, 1])
    
    with col_auth:
        if auth_mode == "Sign Up (Create New Business Account)":
            st.markdown("### 📝 Register Your Business")
            email = st.text_input("User Email Address")
            password = st.text_input("Unique Password", type="password")
            
            st.markdown("---")
            st.markdown("#### 🏢 Business Details")
            biz_name = st.text_input("Business Name (e.g. Ali Traders, Bismillah Pharmacy)")
            biz_type = st.selectbox("Business Type", ["Grocery Store", "Medical Store / Pharmacy", "General Store", "Services / Consulting", "Wholesale", "Other"])
            biz_phone = st.text_input("WhatsApp Business Contact Number")
            
            if st.button("Create Account & Setup Ledger"):
                if email and password and biz_name:
                    user_ref = db.collection('users').document(email.lower()).get()
                    if user_ref.exists:
                        st.error("Account already exists with this email! Please login.")
                    else:
                        hashed_pw = make_hash(password)
                        biz_data = {
                            "email": email.lower(),
                            "password": hashed_pw,
                            "business_name": biz_name,
                            "business_type": biz_type,
                            "phone": biz_phone,
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        db.collection('users').document(email.lower()).set(biz_data)
                        st.success("🎉 Account created successfully! Please switch to 'Login' mode.")
                else:
                    st.warning("Please fill in all required fields (Email, Password, Business Name).")

        elif auth_mode == "Login":
            st.markdown("### 🔑 Client Login")
            login_email = st.text_input("Email Address")
            login_password = st.text_input("Password", type="password")
            
            if st.button("Login to Dashboard"):
                if login_email and login_password:
                    user_doc = db.collection('users').document(login_email.lower()).get()
                    if user_doc.exists:
                        user_data = user_doc.to_dict()
                        if user_data['password'] == make_hash(login_password):
                            st.session_state['logged_in'] = True
                            st.session_state['user_email'] = login_email.lower()
                            st.session_state['business_id'] = login_email.lower()
                            st.session_state['business_details'] = user_data
                            st.success("Login Successful!")
                            st.rerun()
                        else:
                            st.error("Incorrect Password.")
                    else:
                        st.error("User email not found. Please Sign Up first.")
                else:
                    st.warning("Please enter both Email and Password.")

# ------------------ SCREEN 2: MAIN CLIENT DASHBOARD ------------------
else:
    biz_info = st.session_state['business_details']
    
    # Header & Business Branding
    top_c1, top_c2 = st.columns([3, 1])
    with top_c1:
        st.title(f"🏢 {biz_info.get('business_name', 'My Business')}")
        st.caption(f"Category: {biz_info.get('business_type', 'General')} | Account ID: {st.session_state['user_email']}")
    with top_c2:
        if st.button("🚪 Logout"):
            st.session_state['logged_in'] = False
            st.session_state['user_email'] = ""
            st.session_state['business_id'] = ""
            st.session_state['business_details'] = {}
            st.rerun()

    st.divider()

    # Category Mapper & Logic Functions
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
            "business_id": st.session_state['business_id'], # Multi-tenant isolation!
            "raw_sms": sms_text,
            "amount": amount,
            "merchant": merchant,
            "payment_method": payment_method,
            "type": "Debit" if is_debit else "Credit",
            "category": cat,
            "status": "processed",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # Sidebar - Live Input Form with Custom Date
    st.sidebar.header("📩 Add Live SMS Transaction")
    user_sms = st.sidebar.text_area("Paste SMS Text Here:", placeholder="Paid Rs 1,500 to Foodpanda via EasyPaisa.")
    
    custom_date = st.sidebar.date_input("Transaction Date:", value=datetime.now().date())
    custom_time = st.sidebar.time_input("Transaction Time:", value=datetime.now().time())
    entry_timestamp = datetime.combine(custom_date, custom_time).strftime("%Y-%m-%d %H:%M:%S")

    if st.sidebar.button("Process & Save Transaction"):
        if user_sms.strip():
            parsed_record = parse_sms_logic(user_sms)
            parsed_record["timestamp"] = entry_timestamp
            
            db.collection('transactions').add(parsed_record)
            st.sidebar.success("✅ Transaction Saved for Your Business!")
            st.rerun()
        else:
            st.sidebar.warning("Please enter an SMS first.")

    # Fetch Data (STRICTLY ISOLATED BY BUSINESS ID)
    def load_data():
        docs = db.collection('transactions').where('business_id', '==', st.session_state['business_id']).stream()
        data = []
        for doc in docs:
            d = doc.to_dict()
            if "timestamp" not in d or not d["timestamp"]:
                d["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data.append(d)
        if data:
            df_loaded = pd.DataFrame(data)
            df_loaded['timestamp'] = pd.to_datetime(df_loaded['timestamp'], errors='coerce', utc=True)
            df_loaded['timestamp'] = df_loaded['timestamp'].dt.tz_localize(None)
            df_loaded['timestamp'] = df_loaded['timestamp'].fillna(pd.Timestamp.now())
            return df_loaded
        return pd.DataFrame()

    df = load_data()

    if not df.empty:
        # Sidebar Filters
        st.sidebar.divider()
        st.sidebar.header("🔍 Filters & Date Range")

        all_categories = ["All"] + list(df['category'].dropna().unique())
        selected_category = st.sidebar.selectbox("Filter by Category:", all_categories)
        selected_type = st.sidebar.radio("Transaction Type:", ["All", "Debit (Expense)", "Credit (Income)"])

        min_date = df['timestamp'].min().date()
        max_date = df['timestamp'].max().date()

        date_range = st.sidebar.date_input(
            "Select Date Range:",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

        filtered_df = df.copy()

        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[
                (filtered_df['timestamp'].dt.date >= start_date) & 
                (filtered_df['timestamp'].dt.date <= end_date)
            ]

        if selected_category != "All":
            filtered_df = filtered_df[filtered_df['category'] == selected_category]

        if selected_type == "Debit (Expense)":
            filtered_df = filtered_df[filtered_df['type'] == 'Debit']
        elif selected_type == "Credit (Income)":
            filtered_df = filtered_df[filtered_df['type'] == 'Credit']

        # Metrics
        total_income = filtered_df[filtered_df['type'] == 'Credit']['amount'].sum()
        total_expense = filtered_df[filtered_df['type'] == 'Debit']['amount'].sum()
        net_balance = total_income - total_expense

        c1, c2, c3 = st.columns(3)
        c1.metric("Selected Income", f"Rs. {total_income:,.2f}")
        c2.metric("Selected Expenses", f"Rs. {total_expense:,.2f}")
        c3.metric("Net Balance", f"Rs. {net_balance:,.2f}")

        st.divider()

        # Visual Charts
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

        st.divider()

        # Table & Export
        col_table, col_export = st.columns([3, 1])
        with col_table:
            st.subheader("📋 Ledger Transactions")
        
        def convert_df_to_csv(dataframe):
            return dataframe.to_csv(index=False).encode('utf-8')

        def convert_df_to_excel(dataframe):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                dataframe.to_excel(writer, index=False, sheet_name='Filtered Transactions')
            return output.getvalue()

        with col_export:
            st.subheader("📥 Export")
            csv_data = convert_df_to_csv(filtered_df)
            st.download_button(
                label="📄 Export CSV",
                data=csv_data,
                file_name=f"{biz_info.get('business_name', 'ledger')}_transactions.csv",
                mime="text/csv"
            )
            
            excel_data = convert_df_to_excel(filtered_df)
            st.download_button(
                label="📊 Export Excel",
                data=excel_data,
                file_name=f"{biz_info.get('business_name', 'ledger')}_transactions.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        display_df = filtered_df.copy()
        display_df['Date & Time'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(
            display_df[['Date & Time', 'amount', 'merchant', 'category', 'type', 'payment_method', 'status']],
            width='stretch'
        )

    else:
        st.info("No transactions found for this business yet. Use the sidebar to add your first transaction!")