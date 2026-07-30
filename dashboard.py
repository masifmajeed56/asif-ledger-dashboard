import streamlit as st
import pandas as pd
import json
import re
import io
import hashlib
from datetime import datetime
from PIL import Image
from google.cloud import firestore
from google.oauth2 import service_account

# Page Setup
st.set_page_config(page_title="AI Ledger - Multi-Tenant Business Engine", layout="wide")

# Database Connection
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

# Password Hashing
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# Password Strength Validation
def validate_password_strength(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter (A-Z)."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter (a-z)."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one digit (0-9)."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character (!@#$%^&*)."
    return True, "Strong Password"

# Email Format Validation
def validate_email_format(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email) is not None

# Username Suggestions Generator
def generate_username_suggestions(base_username):
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '', base_username.lower())
    suggestions = [
        f"{cleaned}_pk",
        f"{cleaned}_official",
        f"{cleaned}_store",
        f"{cleaned}123",
        f"{cleaned}_ledger"
    ]
    available_suggestions = []
    for sug in suggestions:
        doc = db.collection('usernames').document(sug).get()
        if not doc.exists:
            available_suggestions.append(sug)
        if len(available_suggestions) >= 3:
            break
    return available_suggestions

# Session State Initialization
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = ""
if 'business_id' not in st.session_state:
    st.session_state['business_id'] = ""
if 'business_details' not in st.session_state:
    st.session_state['business_details'] = {}
if 'auth_mode' not in st.session_state:
    st.session_state['auth_mode'] = "Login"

# ------------------ SCREEN 1: LOGIN & ENHANCED SIGNUP ------------------
if not st.session_state['logged_in']:
    st.title("💼 AI Ledger Solutions")
    st.subheader("Multi-Business Cloud Accounting Platform")
    
    # Dynamic Navigation State
    auth_options = ["Login", "Sign Up (Create New Business Account)"]
    selected_mode = st.radio(
        "Choose Action:", 
        auth_options, 
        index=auth_options.index(st.session_state['auth_mode']) if st.session_state['auth_mode'] in auth_options else 0,
        horizontal=True
    )
    st.session_state['auth_mode'] = selected_mode
    st.divider()

    col_auth, _ = st.columns([2, 1])
    
    with col_auth:
        if st.session_state['auth_mode'] == "Sign Up (Create New Business Account)":
            st.markdown("### 📝 Register Your Business")
            
            desired_username = st.text_input("Choose Unique Business Username (e.g. asifledger, ali_store)", help="Only letters, numbers, and underscores allowed.")
            username_clean = re.sub(r'[^a-zA-Z0-9_]', '', desired_username.lower().strip()) if desired_username else ""
            
            username_is_valid = False
            if username_clean:
                user_doc = db.collection('usernames').document(username_clean).get()
                if user_doc.exists:
                    st.error(f"❌ Username '{username_clean}' is already taken!")
                    suggestions = generate_username_suggestions(username_clean)
                    if suggestions:
                        st.info(f"💡 Available Suggestions: {', '.join(suggestions)}")
                else:
                    st.success(f"✅ Username '{username_clean}' is available!")
                    username_is_valid = True

            email = st.text_input("User Email Address")
            password = st.text_input("Unique Password", type="password", help="Must have 8+ chars, Uppercase, Lowercase, Number & Special Character.")
            
            st.markdown("---")
            st.markdown("#### 🏢 Business Details & Branding")
            biz_name = st.text_input("Business Name (e.g. Ali Traders, Bismillah Pharmacy)")
            biz_type = st.selectbox("Business Type", ["Grocery Store", "Medical Store / Pharmacy", "General Store", "Services / Consulting", "Wholesale", "Other"])
            biz_phone = st.text_input("WhatsApp Business Contact Number (e.g. 03001234567)")
            
            logo_file = st.file_uploader("Upload Business Logo (PNG / JPG)", type=["png", "jpg", "jpeg"])
            
            if st.button("Create Account & Setup Ledger"):
                if not username_clean or not username_is_valid:
                    st.error("Please enter a valid and available username.")
                elif not validate_email_format(email):
                    st.error("Please enter a valid email address (e.g. name@domain.com).")
                else:
                    is_pw_strong, pw_msg = validate_password_strength(password)
                    if not is_pw_strong:
                        st.error(f"Password Error: {pw_msg}")
                    elif not biz_name or not biz_phone:
                        st.error("Please fill in Business Name and Phone Number.")
                    else:
                        email_clean = email.lower().strip()
                        user_ref = db.collection('users').document(email_clean).get()
                        if user_ref.exists:
                            st.error("Account already exists with this email! Please login.")
                        else:
                            hashed_pw = make_hash(password)
                            
                            logo_data_str = ""
                            if logo_file is not None:
                                bytes_data = logo_file.getvalue()
                                logo_data_str = bytes_data.hex()

                            biz_data = {
                                "username": username_clean,
                                "email": email_clean,
                                "password": hashed_pw,
                                "business_name": biz_name,
                                "business_type": biz_type,
                                "phone": biz_phone,
                                "logo_hex": logo_data_str,
                                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            db.collection('users').document(email_clean).set(biz_data)
                            db.collection('usernames').document(username_clean).set({"email": email_clean})
                            
                            # Success Banner with Interactive Redirection Link
                            st.success("🎉 Account created successfully!")
                            if st.button("👉 Click here to Login Now"):
                                st.session_state['auth_mode'] = "Login"
                                st.rerun()

        elif st.session_state['auth_mode'] == "Login":
            st.markdown("### 🔑 Client Login")
            login_id = st.text_input("Username or Email Address")
            login_password = st.text_input("Password", type="password")
            
            if st.button("Login to Dashboard"):
                if login_id and login_password:
                    login_clean = login_id.lower().strip()
                    target_email = login_clean
                    
                    if "@" not in login_clean:
                        u_doc = db.collection('usernames').document(login_clean).get()
                        if u_doc.exists:
                            target_email = u_doc.to_dict().get("email", "")
                        else:
                            st.error("Username not found.")
                            target_email = ""

                    if target_email:
                        user_doc = db.collection('users').document(target_email).get()
                        if user_doc.exists:
                            user_data = user_doc.to_dict()
                            if user_data['password'] == make_hash(login_password):
                                st.session_state['logged_in'] = True
                                st.session_state['user_email'] = target_email
                                st.session_state['business_id'] = target_email
                                st.session_state['business_details'] = user_data
                                st.success("Login Successful!")
                                st.rerun()
                            else:
                                st.error("Incorrect Password.")
                        else:
                            st.error("User Account not found.")
                else:
                    st.warning("Please enter credentials.")

# ------------------ SCREEN 2: DASHBOARD & BRANDED LEDGER ------------------
else:
    biz_info = st.session_state['business_details']
    
    top_c1, top_c2, top_c3 = st.columns([1, 3, 1])
    
    with top_c1:
        if biz_info.get("logo_hex"):
            try:
                logo_bytes = bytes.fromhex(biz_info["logo_hex"])
                image = Image.open(io.BytesIO(logo_bytes))
                st.image(image, width=110)
            except Exception:
                st.write("🏢")
        else:
            st.write("🏢")

    with top_c2:
        st.title(f"{biz_info.get('business_name', 'My Business')}")
        st.caption(f"Category: {biz_info.get('business_type', 'General')} | Handle: @{biz_info.get('username', 'business')}")

    with top_c3:
        if st.button("🚪 Logout"):
            st.session_state['logged_in'] = False
            st.session_state['user_email'] = ""
            st.session_state['business_id'] = ""
            st.session_state['business_details'] = {}
            st.session_state['auth_mode'] = "Login"
            st.rerun()

    st.divider()

    # Category Mapper & Enhanced Merchant Parser Logic
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

        merchant = "General Merchant"
        merchant_match = re.search(r'(?:to|at|paid to|sent to|received from|from|transfer from)\s+([A-Za-z0-9\s&]+?)(?=\s+(?:via|on|from|ref|dated|code|\.|$))', sms_text, re.IGNORECASE)
        if merchant_match:
            merchant = merchant_match.group(1).strip()

        method_match = re.search(r'(?:via|using|through)\s+([A-Za-z0-9\s]+?)(?=\s+(?:on|dated|ref|\.|$))', sms_text, re.IGNORECASE)
        payment_method = method_match.group(1).strip() if method_match else "Direct Transfer"

        is_debit = any(word in sms_text.lower() for word in ["paid", "sent", "debited", "spent", "withdrawn"])
        cat = auto_assign_category(merchant, sms_text) if is_debit else "Income"

        return {
            "business_id": st.session_state['business_id'],
            "raw_sms": sms_text,
            "amount": amount,
            "merchant": merchant,
            "payment_method": payment_method,
            "type": "Debit" if is_debit else "Credit",
            "category": cat,
            "status": "processed",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    tab_dashboard, tab_customers = st.tabs(["📊 Main Ledger Dashboard", "👥 Customer Directory & Statements"])

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

    st.sidebar.header("📩 Add Live SMS Transaction")
    user_sms = st.sidebar.text_area("Paste SMS Text Here:", placeholder="Received Rs 5,000 from Ali Traders via EasyPaisa.")
    
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

    with tab_dashboard:
        if not df.empty:
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

            total_income = filtered_df[filtered_df['type'] == 'Credit']['amount'].sum()
            total_expense = filtered_df[filtered_df['type'] == 'Debit']['amount'].sum()
            net_balance = total_income - total_expense

            c1, c2, c3 = st.columns(3)
            c1.metric("Selected Income", f"Rs. {total_income:,.2f}")
            c2.metric("Selected Expenses", f"Rs. {total_expense:,.2f}")
            c3.metric("Net Balance", f"Rs. {net_balance:,.2f}")

            st.divider()

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
                    file_name=f"{biz_info.get('username', 'ledger')}_transactions.csv",
                    mime="text/csv"
                )
                
                excel_data = convert_df_to_excel(filtered_df)
                st.download_button(
                    label="📊 Export Excel",
                    data=excel_data,
                    file_name=f"{biz_info.get('username', 'ledger')}_transactions.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            display_df = filtered_df.copy()
            display_df['Date & Time'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(
                display_df[['Date & Time', 'amount', 'merchant', 'category', 'type', 'payment_method', 'status']],
                width='stretch'
            )
        else:
            st.info("No transactions recorded yet. Add your first transaction from the sidebar!")

    with tab_customers:
        st.subheader("👥 Repeated Customers / Merchants Directory")
        
        if not df.empty:
            merchants_list = sorted(list(df['merchant'].unique()))
            selected_merchant = st.selectbox("Select Customer / Merchant to View Ledger:", merchants_list)
            
            if selected_merchant:
                m_df = df[df['merchant'] == selected_merchant]
                
                m_credit = m_df[m_df['type'] == 'Credit']['amount'].sum()
                m_debit = m_df[m_df['type'] == 'Debit']['amount'].sum()
                
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Total Received (Credit)", f"Rs. {m_credit:,.2f}")
                mc2.metric("Total Paid (Debit)", f"Rs. {m_debit:,.2f}")
                mc3.metric("Net Transaction Volume", f"Rs. {m_credit + m_debit:,.2f}")
                
                st.markdown(f"#### 📜 Statement History for **{selected_merchant}**")
                display_m_df = m_df.copy()
                display_m_df['Date & Time'] = display_m_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
                st.dataframe(
                    display_m_df[['Date & Time', 'amount', 'type', 'category', 'payment_method', 'raw_sms']],
                    width='stretch'
                )
        else:
            st.info("Customer history will appear here once transactions are recorded.")