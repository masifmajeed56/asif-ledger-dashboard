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

# Force Override Streamlit's Default Red Theme with Office Blue
st.markdown("""
<style>
    /* Complete Red Theme Override for Primary Buttons */
    button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"],
    div.stButton > button[kind="primary"] {
        background-color: #003366 !important;
        color: #ffffff !important;
        border-color: #002244 !important;
        background-image: none !important;
        font-weight: bold !important;
    }

    /* Primary Button Hover State */
    button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover,
    div.stButton > button[kind="primary"]:hover {
        background-color: #0056b3 !important;
        color: #ffffff !important;
        border-color: #004085 !important;
        cursor: pointer !important;
    }

    /* Secondary Inactive Buttons Styling */
    button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"],
    div.stButton > button[kind="secondary"] {
        background-color: #f0f2f6 !important;
        color: #333333 !important;
        border: 1px solid #cccccc !important;
    }

    /* Secondary Button Hover State */
    button[kind="secondary"]:hover,
    .stButton > button[data-testid="baseButton-secondary"]:hover,
    div.stButton > button[kind="secondary"]:hover {
        background-color: #0056b3 !important;
        color: #ffffff !important;
        border-color: #004085 !important;
        cursor: pointer !important;
    }

    /* Disabled Button Styling */
    button:disabled,
    button[disabled],
    .stButton > button:disabled {
        background-color: #e0e0e0 !important;
        color: #888888 !important;
        border-color: #cccccc !important;
        cursor: not-allowed !important;
    }

    /* Interactive Link Hover Effects */
    a {
        color: #003366 !important;
        text-decoration: none !important;
        transition: color 0.2s ease-in-out, text-decoration 0.2s ease-in-out;
    }
    a:hover {
        color: #0056b3 !important;
        text-decoration: underline !important;
    }

    .stSelectbox label, .stTextInput label {
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Native Timezone
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

# Country Codes with Flags & Matching Phone Placeholders
COUNTRY_DATA = {
    "🇵🇰 +92": {"code": "92", "placeholder": "3001234567"},
    "🇦🇪 +971": {"code": "971", "placeholder": "501234567"},
    "🇸🇦 +966": {"code": "966", "placeholder": "501234567"},
    "🇬🇧 +44": {"code": "44", "placeholder": "7911123456"},
    "🇺🇸 +1": {"code": "1", "placeholder": "2015550123"},
    "🇨🇦 +1": {"code": "1", "placeholder": "4165550123"},
    "🇮🇳 +91": {"code": "91", "placeholder": "9876543210"},
    "🇧🇩 +880": {"code": "880", "placeholder": "1712345678"},
    "🇶🇦 +974": {"code": "974", "placeholder": "33123456"},
    "🇰🇼 +965": {"code": "965", "placeholder": "50123456"},
    "🇴🇲 +968": {"code": "968", "placeholder": "91234567"},
    "🇧🇭 +973": {"code": "973", "placeholder": "36123456"},
    "🇲🇾 +60": {"code": "60", "placeholder": "123456789"},
    "🇸🇬 +65": {"code": "65", "placeholder": "81234567"},
    "🇦🇺 +61": {"code": "61", "placeholder": "412345678"},
    "🇩🇪 +49": {"code": "49", "placeholder": "15123456789"},
    "🇫🇷 +33": {"code": "33", "placeholder": "612345678"},
    "🇹🇷 +90": {"code": "90", "placeholder": "5012345678"},
    "🇿🇦 +27": {"code": "27", "placeholder": "821234567"}
}

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
if 'saved_accounts_dict' not in st.session_state:
    st.session_state['saved_accounts_dict'] = {}

# Persistent Captcha Logic
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
        if st.button("Login", use_container_width=True, type="primary" if is_login else "secondary", help="Click to switch to the Login form"):
            st.session_state['active_window'] = "Login Window"
            st.rerun()
    with col_w2:
        is_signup = st.session_state['active_window'] == "Signup Window"
        if st.button("Signup", use_container_width=True, type="primary" if is_signup else "secondary", help="Click to switch to the Account Registration form"):
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

        login_id = st.text_input("Username (@handle), Email, or Phone Number", value=preset_login, placeholder="e.g. user_handle, name@email.com, or +923001234567", key="login_id_input")
        login_password = st.text_input("Password", type="password", value=preset_password, key="login_pw_input")

        # Captcha Field
        st.markdown("#### 🤖 Human Verification")
        c_col1, c_col2 = st.columns([4, 1])
        with c_col1:
            login_captcha = st.text_input(f"Question: What is {l_n1} + {l_n2} ? *", placeholder="Enter sum answer", key="login_cap_input")
        with c_col2:
            st.write(" ")
            st.write(" ")
            if st.button("🔄", key="login_cap_reload", help="Click to reload a new simple captcha question"):
                refresh_locked_captcha("login")
                st.rerun()

        # Dynamic State Evaluation to ensure real-time button activation
        val_id = str(st.session_state.get('login_id_input', login_id)).strip()
        val_pw = str(st.session_state.get('login_pw_input', login_password)).strip()
        val_cap = str(st.session_state.get('login_cap_input', login_captcha)).strip()

        login_form_valid = bool(val_id) and bool(val_pw) and bool(val_cap)

        if not login_form_valid:
            st.info("💡 Please fill in your Login ID, Password, and Captcha answer to enable the Login button.")

        # HOVER TOOLTIP SET TO "Submit" + FULLY FUNCTIONAL ENABLED STATE
        submit_login = st.button("🔑 Login to Dashboard", type="primary", disabled=not login_form_valid, help="Submit")

        if submit_login:
            if not val_cap.isnumeric() or int(val_cap) != l_ans:
                refresh_locked_captcha("login")
                st.error("🚨 Incorrect Captcha answer! A new problem has been generated.")
            else:
                login_clean = val_id
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
                        if user_data['password'] == make_hash(val_pw):
                            st.session_state['logged_in'] = True
                            st.session_state['user_email'] = target_email
                            st.session_state['business_id'] = target_email
                            st.session_state['business_details'] = user_data
                            
                            account_label = f"{user_data.get('business_name', 'Business')} (@{user_data.get('username', 'user')})"
                            st.session_state['saved_accounts_dict'][account_label] = {
                                "login": target_email,
                                "password": val_pw
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
            
            entered_otp = st.text_input("Enter 6-Digit OTP Code:", max_chars=6, key="otp_input_key")
            
            otp_val = str(st.session_state.get('otp_input_key', entered_otp)).strip()
            otp_valid = bool(otp_val)
            
            submit_otp = st.button("✅ Verify OTP & Finalize Account", type="primary", disabled=not otp_valid, help="Submit")
            
            if submit_otp:
                if otp_val == st.session_state['generated_otp']:
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
            if st.button("👉 Go to Login Window", help="Click to switch to the account login window"):
                st.session_state['active_window'] = "Login Window"
                st.rerun()

        # SIGNUP FORM STEP
        else:
            st.markdown("### 📝 Create New Business Account")
            
            s_n1, s_n2, s_ans = get_locked_captcha("signup")

            # 1. Email Input & Availability Check
            check_email = st.text_input("User Email Address *", placeholder="name@domain.com", key="live_signup_email")
            email_clean = check_email.lower().strip()
            
            email_already_taken = False
            if email_clean and validate_email_format(email_clean):
                if db.collection('users').document(email_clean).get().exists:
                    email_already_taken = True
                    st.error("🚨 This Email is already registered with another business! Please login or use a different email.")

            # 2. Dynamic Country Code Dropdown & Aligned Phone Placeholder
            st.markdown("#### 📞 Contact Phone Number *")
            p_col1, p_col2 = st.columns([1, 3])
            with p_col1:
                selected_country = st.selectbox("Country Code", list(COUNTRY_DATA.keys()), label_visibility="collapsed")
            
            country_info = COUNTRY_DATA[selected_country]
            dynamic_placeholder = country_info["placeholder"]
            
            with p_col2:
                check_phone = st.text_input("Phone Number", placeholder=dynamic_placeholder, key="live_signup_phone", label_visibility="collapsed")

            phone_clean = re.sub(r'\D', '', check_phone)
            extracted_code = country_info["code"]
            formatted_phone_key = f"+{extracted_code}_{phone_clean}"

            phone_already_taken = False
            if phone_clean:
                if db.collection('phone_numbers').document(formatted_phone_key).get().exists:
                    phone_already_taken = True
                    st.error("🚨 This Phone Number is already linked to an existing business account!")

            # 3. Form Grid
            grid_c1, grid_c2 = st.columns(2)
            
            with grid_c1:
                password = st.text_input("Unique Password *", type="password", placeholder="8+ chars, Uppercase, Number & Symbol", key="signup_pw_key")
                biz_name = st.text_input("Business Name *", placeholder="e.g. Ali Traders, Bismillah Pharmacy", key="signup_biz_key")

            with grid_c2:
                username_input = st.text_input("Choose Unique Username / Handle (Optional)", placeholder="Auto-generated if left empty", key="signup_user_key")
                biz_type = st.selectbox("Business Category", ["Grocery Store", "Medical Store / Pharmacy", "General Store", "Services / Consulting", "Wholesale", "Other"])

            # 4. Math Captcha Section
            st.markdown("#### 🤖 Human Verification")
            sc_col1, sc_col2 = st.columns([4, 1])
            with sc_col1:
                captcha_input = st.text_input(f"Question: What is {s_n1} + {s_n2} ? *", placeholder="Enter sum answer", key="signup_cap_key")
            with sc_col2:
                st.write(" ")
                st.write(" ")
                if st.button("🔄", key="signup_cap_reload", help="Click to reload a new simple captcha question"):
                    refresh_locked_captcha("signup")
                    st.rerun()

            logo_file = st.file_uploader("Upload Business Logo (PNG / JPG)", type=["png", "jpg", "jpeg"])

            # Active Inputs Check
            v_email = str(st.session_state.get('live_signup_email', check_email)).strip()
            v_pw = str(st.session_state.get('signup_pw_key', password)).strip()
            v_biz = str(st.session_state.get('signup_biz_key', biz_name)).strip()
            v_phone = str(st.session_state.get('live_signup_phone', check_phone)).strip()
            v_cap = str(st.session_state.get('signup_cap_key', captcha_input)).strip()

            all_required_filled = bool(v_email) and bool(v_pw) and bool(v_biz) and bool(v_phone) and bool(v_cap)
            
            signup_button_disabled = (not all_required_filled) or email_already_taken or phone_already_taken

            if signup_button_disabled:
                if email_already_taken or phone_already_taken:
                    st.warning("⚠️ Submit button is disabled because the entered Email or Phone Number is already taken.")
                elif not all_required_filled:
                    st.info("💡 Please fill in all required fields (*) to enable the verification button.")

            # HOVER TOOLTIP SET TO "Submit"
            submit_signup = st.button(
                "🚀 Verify & Create Account",
                type="primary",
                disabled=signup_button_disabled,
                help="Submit"
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
                    elif not v_cap.isnumeric() or int(v_cap) != s_ans:
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
        if st.button("🚪 Logout", help="Click to log out safely from your business dashboard session"):
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

    if st.sidebar.button("Process & Save Transaction", help="Click to parse SMS text and save entry into ledger database"):
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
                    help="Click to download filtered transactions in CSV spreadsheet format"
                )
                
                excel_data = convert_df_to_excel(filtered_df)
                st.download_button(
                    label="📊 Export Excel",
                    data=excel_data,
                    file_name=f"{biz_info.get('username', 'ledger')}_transactions.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Click to download filtered transactions in Microsoft Excel format"
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