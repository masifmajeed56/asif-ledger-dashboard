import streamlit as st
import pandas as pd
import json
import re
import io
import hashlib
import random
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image
from google.cloud import firestore
from google.oauth2 import service_account

# Page Setup
st.set_page_config(page_title="Asif Ledger Solutions", layout="wide")

# Custom CSS for Office Blue theme, Link Underlines & Compact Alignment
st.markdown("""
<style>
    /* Office Blue Theme Button Customization */
    div.stButton > button[kind="primary"] {
        background-color: #003366 !important;
        color: #ffffff !important;
        border-color: #002244 !important;
        font-weight: bold;
    }
    
    /* Interactive Link Hover Effects */
    a {
        text-decoration: none;
        transition: color 0.2s ease-in-out, text-decoration 0.2s ease-in-out;
    }
    a:hover {
        color: #0056b3 !important;
        text-decoration: underline !important;
    }

    /* Compact Form Layout Alignment */
    .stSelectbox label, .stTextInput label {
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Native Timezone (Pakistan Standard Time)
def get_current_time():
    return datetime.now(ZoneInfo('Asia/Karachi'))

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

# Worldwide Country Codes List
WORLD_COUNTRY_CODES = [
    "🇵🇰 +92", "🇦🇫 +93", "🇦🇱 +355", "🇩🇿 +213", "🇦🇩 +376", "🇦🇴 +244", "🇦🇷 +54",
    "🇦🇲 +374", "🇦🇺 +61", "🇦🇹 +43", "🇦🇿 +994", "🇧🇭 +973", "🇧🇩 +880", "🇧🇪 +32",
    "🇧🇷 +55", "🇨🇦 +1", "🇨🇳 +86", "🇪🇬 +20", "🇫🇷 +33", "🇩🇪 +49", "🇮🇳 +91",
    "🇮🇩 +62", "🇮🇷 +98", "🇮🇶 +964", "🇮🇪 +353", "🇮🇹 +39", "🇯🇵 +81", "🇯🇴 +962",
    "🇰🇼 +965", "🇲🇾 +60", "🇲🇽 +52", "🇳🇵 +977", "🇳🇱 +31", "🇳🇿 +64", "🇴🇲 +968",
    "🇵🇭 +63", "🇶🇦 +974", "🇷🇺 +7", "🇸🇦 +966", "🇸🇬 +65", "🇿🇦 +27", "🇪🇸 +34",
    "🇱🇰 +94", "🇹🇭 +66", "🇹🇷 +90", "🇦🇪 +971", "🇬🇧 +44", "🇺🇸 +1", "🇿🇼 +263"
]

# Helper Functions
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
if 'active_window' not in st.session_state:
    st.session_state['active_window'] = "Login Window"
if 'otp_step' not in st.session_state:
    st.session_state['otp_step'] = False
if 'generated_otp' not in st.session_state:
    st.session_state['generated_otp'] = ""
if 'pending_user_data' not in st.session_state:
    st.session_state['pending_user_data'] = {}
if 'selected_username' not in st.session_state:
    st.session_state['selected_username'] = ""
if 'saved_accounts_dict' not in st.session_state:
    st.session_state['saved_accounts_dict'] = {}

# Persistent Captcha Generator Logic
def get_locked_captcha(key_prefix):
    n1_key = f"{key_prefix}_c_n1"
    n2_key = f"{key_prefix}_c_n2"
    if n1_key not in st.session_state or n2_key not in st.session_state:
        st.session_state[n1_key] = random.randint(1, 12)
        st.session_state[n2_key] = random.randint(1, 9)
    
    n1 = st.session_state[n1_key]
    n2 = st.session_state[n2_key]
    return n1, n2, n1 + n2

def refresh_locked_captcha(key_prefix):
    st.session_state[f"{key_prefix}_c_n1"] = random.randint(1, 12)
    st.session_state[f"{key_prefix}_c_n2"] = random.randint(1, 9)

# Dialog Popup Functions
@st.dialog("⚠️ Business Account Alert")
def show_not_found_popup():
    st.error("🚨 Business Account Not Found!")
    st.write("No account exists with this Email, Username, or Phone Number. Please create a new account.")
    if st.button("👉 Go to Signup Window Now", help="Click to switch to the account registration window"):
        st.session_state['active_window'] = "Signup Window"
        st.rerun()

# ------------------ SCREEN 1: LOGIN & SIGNUP WINDOWS ------------------
if not st.session_state['logged_in']:
    st.title("💼 Asif Ledger Solutions")
    st.caption("Multi-Tenant Cloud Accounting & Ledger Platform")
    
    col_w1, col_w2, _ = st.columns([1, 1, 2])
    with col_w1:
        is_login = st.session_state['active_window'] == "Login Window"
        if st.button("🔑 Login Window", use_container_width=True, type="primary" if is_login else "secondary", help="Click to access your existing account dashboard"):
            st.session_state['active_window'] = "Login Window"
            st.rerun()
    with col_w2:
        is_signup = st.session_state['active_window'] == "Signup Window"
        if st.button("📝 Signup Window", use_container_width=True, type="primary" if is_signup else "secondary", help="Click to register a new business account"):
            st.session_state['active_window'] = "Signup Window"
            st.rerun()

    st.divider()

    # WINDOW 1: LOGIN WINDOW
    if st.session_state['active_window'] == "Login Window":
        st.markdown("### 🔑 Client Account Login")
        
        saved_dict = st.session_state['saved_accounts_dict']
        selected_acc_key = "-- Select Saved Account --"
        
        if saved_dict:
            selected_acc_key = st.selectbox("💡 Quick Select Saved Account:", ["-- Select Saved Account --"] + list(saved_dict.keys()), help="Select a previously logged in account to autofill details")
        
        preset_login = ""
        preset_password = ""
        
        if selected_acc_key != "-- Select Saved Account --":
            preset_login = saved_dict[selected_acc_key]["login"]
            preset_password = saved_dict[selected_acc_key]["password"]

        l_n1, l_n2, l_ans = get_locked_captcha("login")

        login_id = st.text_input("Username (@handle), Email, or Phone Number", value=preset_login, placeholder="e.g. user_handle, name@email.com, or +923001234567")
        login_password = st.text_input("Password", type="password", value=preset_password)

        # Captcha Field with Integrated Reload Button
        st.markdown("#### 🤖 Human Verification")
        c_col1, c_col2 = st.columns([4, 1])
        with c_col1:
            login_captcha = st.text_input(f"Question: What is {l_n1} + {l_n2} ? *", placeholder="Enter answer", label_visibility="visible")
        with c_col2:
            st.write(" ")
            st.write(" ")
            if st.button("🔄", key="login_cap_reload", help="Click to reload a new simple captcha question"):
                refresh_locked_captcha("login")
                st.rerun()

        # Login Button Validation Rules
        login_btn_disabled = False
        if not login_id.strip() or not login_password.strip() or not login_captcha.strip():
            login_btn_disabled = True

        submit_login = st.button("🔑 Login to Dashboard", type="primary", disabled=login_btn_disabled, help="Authenticate credentials and access your dashboard")

        if submit_login:
            if not login_captcha.strip().isnumeric() or int(login_captcha.strip()) != l_ans:
                refresh_locked_captcha("login")
                st.error("🚨 Incorrect Captcha answer! A new problem has been generated.")
            else:
                login_clean = login_id.strip()
                target_email = ""
                
                if "@" in login_clean:
                    target_email = login_clean.lower()
                else:
                    clean_phone_digits = re.sub(r'\D', '', login_clean)
                    if len(clean_phone_digits) >= 7:
                        phone_docs = db.collection('phone_numbers').stream()
                        for p_doc in phone_docs:
                            if clean_phone_digits in re.sub(r'\D', '', p_doc.id):
                                target_email = p_doc.to_dict().get("email", "")
                                break
                    
                    if not target_email:
                        u_doc = db.collection('usernames').document(login_clean.lower()).get()
                        if u_doc.exists:
                            target_email = u_doc.to_dict().get("email", "")

                if target_email:
                    user_doc = db.collection('users').document(target_email).get()
                    if user_doc.exists:
                        user_data = user_doc.to_dict()
                        if user_data['password'] == make_hash(login_password):
                            st.session_state['logged_in'] = True
                            st.session_state['user_email'] = target_email
                            st.session_state['business_id'] = target_email
                            st.session_state['business_details'] = user_data
                            
                            account_label = f"{user_data.get('business_name', 'Business')} (@{user_data.get('username', 'user')})"
                            st.session_state['saved_accounts_dict'][account_label] = {
                                "login": target_email,
                                "password": login_password
                            }
                            refresh_locked_captcha("login")
                            st.success("Login Successful!")
                            st.rerun()
                        else:
                            st.error("🚨 Incorrect Password! Please try again.")
                    else:
                        show_not_found_popup()
                else:
                    show_not_found_popup()

    # WINDOW 2: SIGNUP WINDOW
    elif st.session_state['active_window'] == "Signup Window":
        
        # OTP STEP
        if st.session_state['otp_step']:
            st.markdown("### 🔐 Verify OTP Security Code")
            st.info(f"An OTP Verification code was dispatched for **{st.session_state['pending_user_data']['email']}**.")
            st.success(f"🔑 Secret OTP Code: **{st.session_state['generated_otp']}**")
            
            entered_otp = st.text_input("Enter 6-Digit OTP Code:", max_chars=6)
            submit_otp = st.button("✅ Verify OTP & Finalize Account", type="primary", help="Verify code to complete registration")
            
            if submit_otp:
                if entered_otp.strip() == st.session_state['generated_otp']:
                    data = st.session_state['pending_user_data']
                    
                    db.collection('users').document(data['email']).set(data)
                    db.collection('usernames').document(data['username']).set({"email": data['email']})
                    db.collection('phone_numbers').document(data['phone_raw']).set({"email": data['email']})
                    
                    st.session_state['otp_step'] = False
                    st.session_state['generated_otp'] = ""
                    st.session_state['pending_user_data'] = {}
                    
                    st.success("🎉 Account Verified & Created Successfully!")
                else:
                    st.error("❌ Invalid OTP Code. Please re-check and enter again.")

            st.markdown("---")
            if st.button("👉 Go to Login Window", help="Switch to login window"):
                st.session_state['active_window'] = "Login Window"
                st.rerun()

        # SIGNUP FORM STEP
        else:
            st.markdown("### 📝 Create New Business Account")
            
            s_n1, s_n2, s_ans = get_locked_captcha("signup")

            # 1. Email Input & Live Availability Check
            check_email = st.text_input("User Email Address *", placeholder="name@domain.com", key="live_signup_email")
            email_clean = check_email.lower().strip()
            
            email_already_taken = False
            if email_clean and validate_email_format(email_clean):
                if db.collection('users').document(email_clean).get().exists:
                    email_already_taken = True
                    st.error("🚨 This Email is already registered with another business! Please login or use a different email.")

            # 2. Compact Combined Country Code + Phone Number Input
            st.markdown("#### 📞 Contact Phone Number *")
            p_col1, p_col2 = st.columns([1, 3])
            with p_col1:
                selected_country = st.selectbox("Code", WORLD_COUNTRY_CODES, label_visibility="collapsed")
            with p_col2:
                check_phone = st.text_input("Phone Number", placeholder="3001234567", key="live_signup_phone", label_visibility="collapsed")

            phone_clean = re.sub(r'\D', '', check_phone)
            extracted_code = re.sub(r'\D', '', selected_country)
            formatted_phone_key = f"+{extracted_code}_{phone_clean}"

            phone_already_taken = False
            if phone_clean:
                if db.collection('phone_numbers').document(formatted_phone_key).get().exists:
                    phone_already_taken = True
                    st.error("🚨 This Phone Number is already linked to an existing business account!")

            # 3. Rest of Form Fields
            grid_c1, grid_c2 = st.columns(2)
            
            with grid_c1:
                password = st.text_input("Unique Password *", type="password", placeholder="8+ chars, Uppercase, Number & Symbol")
                biz_name = st.text_input("Business Name *", placeholder="e.g. Ali Traders, Bismillah Pharmacy")

            with grid_c2:
                username_input = st.text_input("Choose Unique Username / Handle (Optional)", value=st.session_state['selected_username'], placeholder="Auto-generated if left empty")
                biz_type = st.selectbox("Business Category", ["Grocery Store", "Medical Store / Pharmacy", "General Store", "Services / Consulting", "Wholesale", "Other"])

            # 4. Math Captcha Section with Integrated Reload Icon
            st.markdown("#### 🤖 Human Verification")
            sc_col1, sc_col2 = st.columns([4, 1])
            with sc_col1:
                captcha_input = st.text_input(f"Question: What is {s_n1} + {s_n2} ? *", placeholder="Enter answer")
            with sc_col2:
                st.write(" ")
                st.write(" ")
                if st.button("🔄", key="signup_cap_reload", help="Click to reload a new simple captcha question"):
                    refresh_locked_captcha("signup")
                    st.rerun()

            logo_file = st.file_uploader("Upload Business Logo (PNG / JPG)", type=["png", "jpg", "jpeg"])

            # 5. Disable Rules Evaluation Logic
            is_form_incomplete = not check_email.strip() or not password.strip() or not biz_name.strip() or not check_phone.strip() or not captcha_input.strip()
            disable_verify_button = is_form_incomplete or email_already_taken or phone_already_taken

            if disable_verify_button:
                if email_already_taken or phone_already_taken:
                    st.warning("⚠️ Verify button is disabled because the entered Email or Phone Number is already registered.")
                elif is_form_incomplete:
                    st.info("💡 Please fill in all required fields (*) to enable the verification button.")

            submit_signup = st.button(
                "🚀 Verify & Create Account",
                type="primary",
                disabled=disable_verify_button,
                help="Click to generate security OTP and proceed with account creation"
            )

            if submit_signup:
                if not validate_email_format(email_clean):
                    st.error("🚨 Invalid Email Address format!")
                else:
                    is_pw_strong, pw_msg = validate_password_strength(password)
                    if not is_pw_strong:
                        st.error(f"🚨 Weak Password! {pw_msg}")
                    elif len(biz_name.strip()) < 3 or biz_name.strip().isnumeric():
                        st.error("🚨 Please enter a valid Business Name (at least 3 characters).")
                    elif not captcha_input.strip().isnumeric() or int(captcha_input.strip()) != s_ans:
                        refresh_locked_captcha("signup")
                        st.error("🚨 Incorrect Captcha answer! A new problem has been generated.")
                    else:
                        final_username = re.sub(r'[^a-zA-Z0-9_]', '', username_input.lower().strip())
                        if not final_username:
                            auto_sugs = generate_username_suggestions(biz_name if biz_name else email_clean)
                            final_username = auto_sugs[0] if auto_sugs else "biz_ledger_account"

                        logo_data_str = logo_file.getvalue().hex() if logo_file is not None else ""

                        generated_code = str(random.randint(100000, 999999))
                        st.session_state['pending_user_data'] = {
                            "username": final_username,
                            "email": email_clean,
                            "password_raw": password,
                            "password": make_hash(password),
                            "business_name": biz_name.strip(),
                            "business_type": biz_type,
                            "phone": f"+{extracted_code} {phone_clean}",
                            "phone_raw": formatted_phone_key,
                            "logo_hex": logo_data_str,
                            "created_at": get_current_time().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        st.session_state['generated_otp'] = generated_code
                        st.session_state['otp_step'] = True
                        refresh_locked_captcha("signup")
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
        if st.button("🚪 Logout", help="Logout from your business account safely"):
            st.session_state['logged_in'] = False
            st.session_state['user_email'] = ""
            st.session_state['business_id'] = ""
            st.session_state['business_details'] = {}
            st.session_state['active_window'] = "Login Window"
            st.session_state['otp_step'] = False
            st.rerun()

    st.divider()

    # Category Mapper & Merchant Parser Logic
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
            "timestamp": get_current_time().strftime("%Y-%m-%d %H:%M:%S")
        }

    tab_dashboard, tab_customers = st.tabs(["📊 Main Ledger Dashboard", "👥 Customer Directory & Statements"])

    def load_data():
        docs = db.collection('transactions').where('business_id', '==', st.session_state['business_id']).stream()
        data = []
        for doc in docs:
            d = doc.to_dict()
            if "timestamp" not in d or not d["timestamp"]:
                d["timestamp"] = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
            data.append(d)
        if data:
            df_loaded = pd.DataFrame(data)
            df_loaded['timestamp'] = pd.to_datetime(df_loaded['timestamp'], errors='coerce', utc=True)
            df_loaded['timestamp'] = df_loaded['timestamp'].dt.tz_localize(None)
            df_loaded['timestamp'] = df_loaded['timestamp'].fillna(pd.Timestamp.now())
            return df_loaded
        return pd.DataFrame()

    df = load_data()

    # Sidebar SMS Entry
    st.sidebar.header("📩 Add Live SMS Transaction")
    user_sms = st.sidebar.text_area("Paste SMS Text Here:", placeholder="Received Rs 5,000 from Ali Traders via EasyPaisa.")
    
    current_now = get_current_time()
    custom_date = st.sidebar.date_input("Transaction Date:", value=current_now.date())
    custom_time = st.sidebar.time_input("Transaction Time:", value=current_now.time())
    entry_timestamp = datetime.combine(custom_date, custom_time).strftime("%Y-%m-%d %H:%M:%S")

    if st.sidebar.button("Process & Save Transaction", help="Parse SMS text and post entry into ledger database"):
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
                    mime="text/csv",
                    help="Download filtered transactions in CSV spreadsheet format"
                )
                
                excel_data = convert_df_to_excel(filtered_df)
                st.download_button(
                    label="📊 Export Excel",
                    data=excel_data,
                    file_name=f"{biz_info.get('username', 'ledger')}_transactions.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Download filtered transactions in Microsoft Excel format"
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
            selected_merchant = st.selectbox("Select Customer / Merchant to View Ledger:", merchants_list, help="Filter detailed transaction statement for a specific client")
            
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