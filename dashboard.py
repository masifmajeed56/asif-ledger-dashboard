import streamlit as st
import pandas as pd
import json
import re
import io
import hashlib
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from PIL import Image
from google.cloud import firestore
from google.oauth2 import service_account

# Page Setup
st.set_page_config(page_title="Asif Ledger Solutions - PC Edition", layout="wide")

# Session State Initializations
if 'active_window' not in st.session_state:
    st.session_state['active_window'] = "Login Window"

if 'del_selected_btn' not in st.session_state:
    st.session_state['del_selected_btn'] = 'left'

if 'reactivate_selected_btn' not in st.session_state:
    st.session_state['reactivate_selected_btn'] = 'left'

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = ""
if 'business_id' not in st.session_state:
    st.session_state['business_id'] = ""
if 'business_details' not in st.session_state:
    st.session_state['business_details'] = {}
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = "Owner"  # Default Owner
if 'otp_step' not in st.session_state:
    st.session_state['otp_step'] = False
if 'generated_otp' not in st.session_state:
    st.session_state['generated_otp'] = ""
if 'pending_user_data' not in st.session_state:
    st.session_state['pending_user_data'] = {}
if 'saved_accounts_dict' not in st.session_state:
    st.session_state['saved_accounts_dict'] = {}
if 'del_step' not in st.session_state:
    st.session_state['del_step'] = 1
if 'show_delete_dialog' not in st.session_state:
    st.session_state['show_delete_dialog'] = False
if 'reactivate_prompt' not in st.session_state:
    st.session_state['reactivate_prompt'] = False
if 'pending_login_data' not in st.session_state:
    st.session_state['pending_login_data'] = {}

# NATIVE CSS OVERRIDES
st.markdown("""
<style>
    button[kind="primary"],
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #003366 !important;
        color: #ffffff !important;
        border: 1px solid #002244 !important;
        font-weight: bold !important;
        transition: all 0.3s ease-in-out !important;
    }
    button[kind="primary"]:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        background-color: #002244 !important;
        color: #ffffff !important;
        border-color: #001122 !important;
        cursor: pointer !important;
        box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.25) !important;
    }
    button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #003366 !important;
        border: 1px solid #003366 !important;
        font-weight: bold !important;
        transition: all 0.3s ease-in-out !important;
    }
    button[kind="secondary"]:hover {
        background-color: #e6f0fa !important;
        color: #002244 !important;
        border-color: #002244 !important;
        cursor: pointer !important;
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

# Country Codes Data
COUNTRY_DATA = {
    "🇵🇰 +92": {"code": "92", "placeholder": "300 1234567", "length": 10, "format_example": "+92 300 1234567"},
    "🇦🇪 +971": {"code": "971", "placeholder": "50 1234567", "length": 9, "format_example": "+971 50 1234567"},
    "🇸🇦 +966": {"code": "966", "placeholder": "50 1234567", "length": 9, "format_example": "+966 50 1234567"},
    "🇬🇧 +44": {"code": "44", "placeholder": "7911 123456", "length": 10, "format_example": "+44 7911 123456"},
    "🇺🇸 +1": {"code": "1", "placeholder": "201 555 0123", "length": 10, "format_example": "+1 201 555 0123"}
}

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def mask_sensitive_text(text, role):
    """Masks phone numbers and private details if user is an Accountant"""
    if role == "Owner":
        return text
    if not text:
        return ""
    # Mask phone numbers or emails
    if len(text) > 4:
        return text[:2] + "******" + text[-2:]
    return "*****"

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

def get_locked_captcha(key_prefix):
    n1_key = f"{key_prefix}_c_n1"
    n2_key = f"{key_prefix}_c_n2"
    if n1_key not in st.session_state or n2_key not in st.session_state:
        st.session_state[n1_key] = random.randint(1, 12)
        st.session_state[n2_key] = random.randint(1, 9)
    return st.session_state[n1_key], st.session_state[n2_key], st.session_state[n1_key] + st.session_state[n2_key]

def refresh_locked_captcha(key_prefix):
    st.session_state[f"{key_prefix}_c_n1"] = random.randint(1, 12)
    st.session_state[f"{key_prefix}_c_n2"] = random.randint(1, 9)

# Dialogs & Verification Popups
@st.dialog("⚠️ Business Account Alert")
def show_not_found_popup():
    st.error("🚨 Business Account Not Found!")
    st.write("No account exists with this Email, Username, or Phone Number. Please create a new account.")
    if st.button("👉 Go to Signup Window Now", type="primary", use_container_width=True):
        st.session_state['active_window'] = "Signup Window"
        st.rerun()

# MAIN SCREEN: LOGIN & SIGNUP ENGINE
if not st.session_state['logged_in']:
    st.title("💼 Asif Ledger Solutions - PC Edition")
    st.caption("Multi-Tenant Cloud & Offline Desktop Accounting Platform")
    
    col_w1, col_w2, _ = st.columns([1, 1, 2])
    login_btn_type = "primary" if st.session_state['active_window'] == "Login Window" else "secondary"
    signup_btn_type = "primary" if st.session_state['active_window'] == "Signup Window" else "secondary"

    with col_w1:
        if st.button("🔑 Login", type=login_btn_type, use_container_width=True):
            st.session_state['active_window'] = "Login Window"
            st.rerun()

    with col_w2:
        if st.button("📝 Signup", type=signup_btn_type, use_container_width=True):
            st.session_state['active_window'] = "Signup Window"
            st.rerun()

    st.divider()

    # ---------------- LOGIN WINDOW ----------------
    if st.session_state['active_window'] == "Login Window":
        st.markdown("### 🔑 Client & Team Login")
        
        login_id_live = st.text_input("Username (@handle), Email, or Phone Number", placeholder="e.g. user_handle, name@email.com, or +923001234567", key="login_id_live_key")
        login_clean_check = login_id_live.strip()

        l_n1, l_n2, l_ans = get_locked_captcha("login")

        with st.form("login_form", clear_on_submit=False):
            login_password = st.text_input("Password", type="password")
            login_captcha = st.text_input(f"Question: What is {l_n1} + {l_n2} ? *", placeholder="Enter sum answer")
            submit_login = st.form_submit_button("Submit")

        if submit_login:
            val_id = str(login_id_live).strip()
            val_pw = str(login_password).strip()
            val_cap = str(login_captcha).strip()

            if not val_id or not val_pw or not val_cap:
                st.warning("⚠️ Please fill in all login fields.")
            elif not val_cap.isnumeric() or int(val_cap) != l_ans:
                refresh_locked_captcha("login")
                st.error("🚨 Incorrect Captcha answer!")
            else:
                target_email = ""
                user_role = "Owner"
                
                # Check Primary Users (Owners)
                if "@" in val_id:
                    target_email = val_id.lower()
                else:
                    u_doc = db.collection('usernames').document(val_id.lower()).get()
                    if u_doc.exists:
                        target_email = u_doc.to_dict().get("email", "")

                user_doc = db.collection('users').document(target_email).get()
                
                # If not Owner, Check Accountant Logins
                if not user_doc.exists:
                    acc_query = db.collection('accountants').where('username', '==', val_id.lower()).stream()
                    for acc in acc_query:
                        acc_data = acc.to_dict()
                        if acc_data['password'] == make_hash(val_pw):
                            target_email = acc_data['owner_email']
                            user_doc = db.collection('users').document(target_email).get()
                            user_role = "Accountant"
                            break

                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    valid_login = False
                    
                    if user_role == "Owner" and user_data['password'] == make_hash(val_pw):
                        valid_login = True
                    elif user_role == "Accountant":
                        valid_login = True

                    if valid_login:
                        st.session_state['logged_in'] = True
                        st.session_state['user_email'] = target_email
                        st.session_state['business_id'] = target_email
                        st.session_state['business_details'] = user_data
                        st.session_state['user_role'] = user_role
                        st.toast(f"Logged in as {user_role}!")
                        st.rerun()
                    else:
                        st.error("🚨 Incorrect Password!")
                else:
                    show_not_found_popup()

    # ---------------- SIGNUP WINDOW ----------------
    elif st.session_state['active_window'] == "Signup Window":
        st.markdown("### 📝 Create Owner Business Account")
        check_email = st.text_input("User Email Address *", placeholder="name@domain.com", key="live_signup_email")
        email_clean = check_email.lower().strip()
        
        p_col1, p_col2 = st.columns([1.2, 2.8])
        with p_col1:
            selected_country = st.selectbox("Country Code", list(COUNTRY_DATA.keys()), key="live_country_select")
        country_info = COUNTRY_DATA[selected_country]
        with p_col2:
            check_phone = st.text_input(f"Phone Number (Max {country_info['length']} digits)", placeholder=country_info["placeholder"], key=f"phone_input_{selected_country}")

        phone_clean = re.sub(r'\D', '', check_phone)
        formatted_phone_key = f"+{country_info['code']}_{phone_clean}"

        s_n1, s_n2, s_ans = get_locked_captcha("signup")

        with st.form("signup_form"):
            password = st.text_input("Unique Password *", type="password")
            biz_name = st.text_input("Business Name *")
            username_input = st.text_input("Choose Unique Username / Handle (Optional)")
            biz_type = st.selectbox("Business Category", ["Services / Consulting", "Wholesale", "Retail", "Other"])
            captcha_input = st.text_input(f"Question: What is {s_n1} + {s_n2} ? *")
            submit_signup = st.form_submit_button("Submit")

        if submit_signup:
            if not email_clean or not password or not biz_name or not captcha_input:
                st.warning("⚠️ Fill in required fields.")
            elif not str(captcha_input).strip().isnumeric() or int(captcha_input) != s_ans:
                refresh_locked_captcha("signup")
                st.error("🚨 Incorrect Captcha!")
            else:
                final_username = re.sub(r'[^a-zA-Z0-9_]', '', username_input.lower().strip()) or email_clean.split("@")[0]
                user_payload = {
                    "username": final_username,
                    "email": email_clean,
                    "password": make_hash(password),
                    "business_name": biz_name.strip(),
                    "business_type": biz_type,
                    "phone": f"+{country_info['code']} {phone_clean}",
                    "phone_raw": formatted_phone_key,
                    "status": "active",
                    "created_at": get_current_time().strftime("%Y-%m-%d %H:%M:%S")
                }
                db.collection('users').document(email_clean).set(user_payload)
                db.collection('usernames').document(final_username).set({"email": email_clean})
                db.collection('phone_numbers').document(formatted_phone_key).set({"email": email_clean})
                
                st.session_state['logged_in'] = True
                st.session_state['user_email'] = email_clean
                st.session_state['business_id'] = email_clean
                st.session_state['business_details'] = user_payload
                st.session_state['user_role'] = "Owner"
                st.rerun()

# ------------------ DASHBOARD VIEW ------------------
else:
    biz_info = st.session_state['business_details']
    role = st.session_state['user_role']
    
    top_c1, top_c2, top_c3 = st.columns([1, 3, 1])
    with top_c1:
        st.write("🏢")
    with top_c2:
        st.title(f"{biz_info.get('business_name', 'My Business')}")
        st.caption(f"Role: **{role}** | Handle: @{biz_info.get('username', 'business')} | Contact: {mask_sensitive_text(biz_info.get('phone', ''), role)}")

    with top_c3:
        if st.button("🚪 Logout", type="secondary"):
            st.session_state['logged_in'] = False
            st.session_state['user_email'] = ""
            st.session_state['user_role'] = "Owner"
            st.rerun()

    st.divider()

    # TABS FOR PC SOFTWARE
    if role == "Owner":
        tab_dash, tab_acc, tab_team = st.tabs(["📊 Main Ledger", "📚 Chart of Accounts", "👥 Team Management (RBAC)"])
    else:
        tab_dash, tab_acc = st.tabs(["📊 Main Ledger", "📚 Chart of Accounts"])

    # TEAM MANAGEMENT TAB (ONLY OWNER ACCESS)
    if role == "Owner":
        with tab_team:
            st.subheader("👥 Accountant Management (Max 2 Allowed)")
            st.info("Assign Accountants restricted access to add/view ledger entries without seeing private customer info.")
            
            # Fetch Current Accountants
            acc_docs = list(db.collection('accountants').where('owner_email', '==', st.session_state['user_email']).stream())
            current_count = len(acc_docs)
            
            st.write(f"**Current Accountants Added:** `{current_count} / 2`")
            
            if acc_docs:
                acc_list = []
                for a in acc_docs:
                    d = a.to_dict()
                    acc_list.append({"Accountant Username": d.get("username"), "Created At": d.get("created_at")})
                st.table(pd.DataFrame(acc_list))

            if current_count < 2:
                with st.form("add_accountant_form"):
                    st.write("### ➕ Add New Accountant")
                    acc_user = st.text_input("Accountant Username *")
                    acc_pass = st.text_input("Accountant Password *", type="password")
                    submit_acc = st.form_submit_button("Create Accountant Account")

                if submit_acc:
                    acc_clean = re.sub(r'[^a-zA-Z0-9_]', '', acc_user.lower().strip())
                    if not acc_clean or not acc_pass:
                        st.warning("Please fill all fields.")
                    else:
                        db.collection('accountants').document(acc_clean).set({
                            "username": acc_clean,
                            "password": make_hash(acc_pass),
                            "owner_email": st.session_state['user_email'],
                            "created_at": get_current_time().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        st.success(f"✅ Accountant `{acc_clean}` created successfully!")
                        st.rerun()
            else:
                st.warning("⚠️ Maximum limit of 2 Accountants reached.")

    with tab_dash:
        st.write("📊 **Ledger Entries & Management Active**")
        st.caption("Entries created here are tracked with user role tags.")