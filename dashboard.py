import streamlit as st
import pandas as pd
import json
import re
import io
import hashlib
import random
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

# Dynamic Country Rules & Formats Matrix
COUNTRY_RULES = {
    "🇵🇰 Pakistan (+92)": {
        "code": "+92",
        "mask": "+923XX-XXXXXXX or 03XX-XXXXXXX",
        "regex": r"^(03\d{9}|3\d{9})$"
    },
    "🇮🇳 India (+91)": {
        "code": "+91",
        "mask": "+91XXXXX-XXXXX",
        "regex": r"^[6-9]\d{9}$"
    },
    "🇦🇪 UAE (+971)": {
        "code": "+971",
        "mask": "+9715X-XXXXXXX",
        "regex": r"^5\d{8}$"
    },
    "🇸🇦 Saudi Arabia (+966)": {
        "code": "+966",
        "mask": "+9665X-XXXXXXX",
        "regex": r"^5\d{8}$"
    },
    "🇺🇸 USA / Canada (+1)": {
        "code": "+1",
        "mask": "+1 (XXX) XXX-XXXX",
        "regex": r"^[2-9]\d{9}$"
    },
    "🇬🇧 UK (+44)": {
        "code": "+44",
        "mask": "+447XXX-XXXXXX",
        "regex": r"^7\d{9}$"
    }
}

# Helpers
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

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

def validate_email_format(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return re.match(pattern, email) is not None

def generate_username_suggestions(base_text):
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '', base_text.lower().replace(" ", "_"))
    if not cleaned:
        cleaned = "biz_ledger"
    suggestions = [f"{cleaned}_pk", f"{cleaned}_official", f"{cleaned}_store", f"{cleaned}123", f"{cleaned}_ledger"]
    available = []
    for sug in suggestions:
        doc = db.collection('usernames').document(sug).get()
        if not doc.exists:
            available.append(sug)
        if len(available) >= 3:
            break
    return available

# Session State Initializations
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
if 'otp_step' not in st.session_state:
    st.session_state['otp_step'] = False
if 'generated_otp' not in st.session_state:
    st.session_state['generated_otp'] = ""
if 'pending_user_data' not in st.session_state:
    st.session_state['pending_user_data'] = {}
if 'selected_username' not in st.session_state:
    st.session_state['selected_username'] = ""
if 'saved_accounts' not in st.session_state:
    st.session_state['saved_accounts'] = []
if 'popup_error' not in st.session_state:
    st.session_state['popup_error'] = ""

# Captcha Generator Function
def generate_math_captcha(key_prefix):
    if f"{key_prefix}_num1" not in st.session_state:
        st.session_state[f"{key_prefix}_num1"] = random.randint(5, 20)
        st.session_state[f"{key_prefix}_num2"] = random.randint(1, 10)
    num1 = st.session_state[f"{key_prefix}_num1"]
    num2 = st.session_state[f"{key_prefix}_num2"]
    return num1, num2, num1 + num2

def refresh_math_captcha(key_prefix):
    st.session_state[f"{key_prefix}_num1"] = random.randint(5, 20)
    st.session_state[f"{key_prefix}_num2"] = random.randint(1, 10)

# Popup Dialog for Error Notifications
@st.dialog("⚠️ Validation Alert")
def show_error_dialog(message, offer_login=False):
    st.error(message)
    if offer_login:
        if st.button("👉 Switch to Login Mode Now"):
            st.session_state['auth_mode'] = "Login"
            st.rerun()
    if st.button("Close"):
        st.rerun()

# ------------------ SCREEN 1: LOGIN & SIGNUP WITH OTP ------------------
if not st.session_state['logged_in']:
    st.title("💼 AI Ledger Solutions")
    st.subheader("Multi-Business Cloud Accounting Platform")
    
    auth_options = ["Login", "Sign Up (Create New Business Account)"]
    selected_mode = st.radio(
        "Choose Action:", 
        auth_options, 
        index=auth_options.index(st.session_state['auth_mode']) if st.session_state['auth_mode'] in auth_options else 0,
        horizontal=True
    )
    st.session_state['auth_mode'] = selected_mode
    st.divider()

    # Dynamic Popup Trigger
    if st.session_state['popup_error']:
        err_msg = st.session_state['popup_error']
        st.session_state['popup_error'] = ""
        offer = "already exists" in err_msg.lower()
        show_error_dialog(err_msg, offer_login=offer)

    col_main, _ = st.columns([2.2, 0.8])
    
    with col_main:
        if st.session_state['auth_mode'] == "Sign Up (Create New Business Account)":
            
            # OTP VERIFICATION STEP WINDOW
            if st.session_state['otp_step']:
                st.markdown("### 🔐 Verify OTP Security Code")
                st.info(f"An OTP Verification code was dispatched for **{st.session_state['pending_user_data']['email']}**.")
                st.success(f"🔑 Secret OTP Code: **{st.session_state['generated_otp']}**")
                
                with st.form(key="otp_form"):
                    entered_otp = st.text_input("Enter 6-Digit OTP Code:", max_chars=6)
                    submit_otp = st.form_submit_button("✅ Verify OTP & Finalize Account")
                    
                    if submit_otp:
                        if entered_otp.strip() == st.session_state['generated_otp']:
                            data = st.session_state['pending_user_data']
                            db.collection('users').document(data['email']).set(data)
                            db.collection('usernames').document(data['username']).set({"email": data['email']})
                            
                            st.session_state['otp_step'] = False
                            st.session_state['generated_otp'] = ""
                            st.session_state['pending_user_data'] = {}
                            
                            st.success("🎉 Account Verified & Created Successfully!")
                        else:
                            st.session_state['popup_error'] = "Invalid OTP Code. Please re-check and enter again."
                            st.rerun()

                st.markdown("---")
                if st.button("👉 Go to Login Screen"):
                    st.session_state['auth_mode'] = "Login"
                    st.rerun()

            # SIGNUP FORM STEP
            else:
                st.markdown("### 📝 Register Your Business Account")
                
                with st.form(key="signup_form"):
                    # PC Grid View (2 Columns) / Mobile Stacked
                    grid_c1, grid_c2 = st.columns(2)
                    
                    with grid_c1:
                        email = st.text_input("User Email Address *", placeholder="name@domain.com")
                        password = st.text_input("Unique Password *", type="password", placeholder="8+ chars, Uppercase, Number & Symbol")
                        biz_name = st.text_input("Business Name *", placeholder="e.g. Ali Traders, Bismillah Pharmacy")
                    
                    with grid_c2:
                        username_input = st.text_input("Choose Unique Username / Handle (Optional)", value=st.session_state['selected_username'], placeholder="Auto-generated if left empty")
                        biz_type = st.selectbox("Business Category", ["Grocery Store", "Medical Store / Pharmacy", "General Store", "Services / Consulting", "Wholesale", "Other"])
                        selected_country_key = st.selectbox("Select Country *", list(COUNTRY_RULES.keys()))

                    rule = COUNTRY_RULES[selected_country_key]
                    phone_num = st.text_input("Mobile / WhatsApp Number *", placeholder=f"Format: {rule['mask']}")
                    
                    # Math Captcha
                    st.markdown("#### 🤖 Human Verification")
                    n1, n2, ans = generate_math_captcha("signup")
                    captcha_input = st.text_input(f"Security Question: What is {n1} + {n2} ? *", placeholder="Enter answer")

                    logo_file = st.file_uploader("Upload Business Logo (PNG / JPG)", type=["png", "jpg", "jpeg"])

                    submit_signup = st.form_submit_button("🚀 Verify & Create Account")

                # Handle Clickable Username Suggestions Outside Form
                if username_input:
                    u_clean = re.sub(r'[^a-zA-Z0-9_]', '', username_input.lower().strip())
                    if u_clean:
                        u_doc = db.collection('usernames').document(u_clean).get()
                        if u_doc.exists:
                            st.warning(f"⚠️ Handle '@{u_clean}' is already taken! Click a suggestion below:")
                            sugs = generate_username_suggestions(u_clean)
                            s_cols = st.columns(len(sugs))
                            for idx, sug in enumerate(sugs):
                                if s_cols[idx].button(f"@{sug}"):
                                    st.session_state['selected_username'] = sug
                                    st.rerun()

                if submit_signup:
                    email_clean = email.lower().strip()
                    clean_phone = re.sub(r'\D', '', phone_num)
                    
                    # 1. Email Check
                    if not validate_email_format(email_clean):
                        st.session_state['popup_error'] = "Invalid Email Address format! Please enter a valid email (e.g. name@domain.com)."
                        st.rerun()
                    
                    user_ref = db.collection('users').document(email_clean).get()
                    if user_ref.exists:
                        st.session_state['popup_error'] = f"An account already exists with email '{email_clean}'! Please switch to Login mode."
                        st.rerun()

                    # 2. Password Check
                    is_pw_strong, pw_msg = validate_password_strength(password)
                    if not is_pw_strong:
                        st.session_state['popup_error'] = f"Weak Password! {pw_msg}"
                        st.rerun()

                    # 3. Business Name Check
                    if len(biz_name.strip()) < 3 or biz_name.strip().isnumeric():
                        st.session_state['popup_error'] = "Please enter a valid Business Name (at least 3 characters)."
                        st.rerun()

                    # 4. Username Auto-Generation or Check
                    final_username = re.sub(r'[^a-zA-Z0-9_]', '', username_input.lower().strip())
                    if not final_username:
                        auto_sugs = generate_username_suggestions(biz_name if biz_name else email_clean)
                        final_username = auto_sugs[0] if auto_sugs else "biz_ledger_account"
                    else:
                        u_doc = db.collection('usernames').document(final_username).get()
                        if u_doc.exists:
                            st.session_state['popup_error'] = f"Username '@{final_username}' is already taken. Please pick another or click a suggestion."
                            st.rerun()

                    # 5. Phone Check
                    if not re.match(rule['regex'], clean_phone):
                        st.session_state['popup_error'] = f"Invalid number! Required Format: {rule['mask']}"
                        st.rerun()

                    # 6. Captcha Check
                    if not captcha_input.strip().isnumeric() or int(captcha_input.strip()) != ans:
                        refresh_math_captcha("signup")
                        st.session_state['popup_error'] = "Incorrect Captcha answer! Please try the new math problem."
                        st.rerun()

                    # Logo Process
                    logo_data_str = logo_file.getvalue().hex() if logo_file is not None else ""

                    # Save Temporary Data and Open OTP
                    generated_code = str(random.randint(100000, 999999))
                    st.session_state['pending_user_data'] = {
                        "username": final_username,
                        "email": email_clean,
                        "password": make_hash(password),
                        "business_name": biz_name.strip(),
                        "business_type": biz_type,
                        "phone": f"{rule['code']} {clean_phone}",
                        "logo_hex": logo_data_str,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    st.session_state['generated_otp'] = generated_code
                    st.session_state['otp_step'] = True
                    st.rerun()

                st.markdown("---")
                if st.button("👉 Already have an account? Click here to Login"):
                    st.session_state['auth_mode'] = "Login"
                    st.rerun()

        elif st.session_state['auth_mode'] == "Login":
            st.markdown("### 🔑 Client Login")
            
            # Saved Accounts Quick Picker
            if st.session_state['saved_accounts']:
                selected_acc = st.selectbox("💡 Quick Select Saved Account:", ["-- Select Saved Account --"] + st.session_state['saved_accounts'])
                if selected_acc != "-- Select Saved Account --":
                    st.session_state['preset_login_id'] = selected_acc
            
            preset_id = st.session_state.get('preset_login_id', '')

            with st.form(key="login_form"):
                login_id = st.text_input("Username (@handle) or Email Address", value=preset_id)
                login_password = st.text_input("Password", type="password")
                
                # Math Captcha for Login
                st.markdown("#### 🤖 Security Check")
                n1, n2, ans = generate_math_captcha("login")
                login_captcha = st.text_input(f"What is {n1} + {n2} ? *", placeholder="Enter answer")

                submit_login = st.form_submit_button("Login to Dashboard")

            if submit_login:
                login_clean = login_id.lower().strip()
                
                if not login_captcha.strip().isnumeric() or int(login_captcha.strip()) != ans:
                    refresh_math_captcha("login")
                    st.session_state['popup_error'] = "Incorrect Captcha answer! Please solve the new problem."
                    st.rerun()

                if login_clean and login_password:
                    target_email = login_clean
                    if "@" not in login_clean:
                        u_doc = db.collection('usernames').document(login_clean).get()
                        if u_doc.exists:
                            target_email = u_doc.to_dict().get("email", "")
                        else:
                            st.session_state['popup_error'] = "Username handle not found!"
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
                                
                                # Save account to recent list
                                handle = user_data.get('username', target_email)
                                if handle not in st.session_state['saved_accounts']:
                                    st.session_state['saved_accounts'].append(handle)

                                st.success("Login Successful!")
                                st.rerun()
                            else:
                                st.session_state['popup_error'] = "Incorrect Password! Please try again."
                                st.rerun()
                        else:
                            st.session_state['popup_error'] = "User Account not found!"
                            st.rerun()
                else:
                    st.session_state['popup_error'] = "Please fill in all required fields."
                    st.rerun()

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
        st.caption(f"Category: {biz_info.get('business_type', 'General')} | Handle: @{biz_info.get('username', 'business')} | Contact: {biz_info.get('phone', '')}")

    with top_c3:
        if st.button("🚪 Logout"):
            st.session_state['logged_in'] = False
            st.session_state['user_email'] = ""
            st.session_state['business_id'] = ""
            st.session_state['business_details'] = {}
            st.session_state['auth_mode'] = "Login"
            st.session_state['otp_step'] = False
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

    # Sidebar SMS Entry with Auto Live Date & Time
    st.sidebar.header("📩 Add Live SMS Transaction")
    user_sms = st.sidebar.text_area("Paste SMS Text Here:", placeholder="Received Rs 5,000 from Ali Traders via EasyPaisa.")
    
    # Auto Live Date & Time
    now = datetime.now()
    custom_date = st.sidebar.date_input("Transaction Date:", value=now.date())
    custom_time = st.sidebar.time_input("Transaction Time:", value=now.time())
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