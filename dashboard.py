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

# Native Timezone
def get_current_time():
    return datetime.now(ZoneInfo('Asia/Karachi'))

def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# ---------------- PERSISTENT SESSION VIA QUERY PARAMS ----------------
query_params = st.query_params
session_email = query_params.get("user", "")
session_role = query_params.get("role", "Owner")

if 'logged_in' not in st.session_state:
    if session_email:
        user_doc = db.collection('users').document(session_email).get()
        if user_doc.exists:
            st.session_state['logged_in'] = True
            st.session_state['user_email'] = session_email
            st.session_state['business_id'] = session_email
            st.session_state['business_details'] = user_doc.to_dict()
            st.session_state['user_role'] = session_role
        else:
            st.session_state['logged_in'] = False
    else:
        st.session_state['logged_in'] = False

if 'active_window' not in st.session_state:
    st.session_state['active_window'] = "Login Window"

if 'del_selected_btn' not in st.session_state:
    st.session_state['del_selected_btn'] = 'left'

if 'reactivate_selected_btn' not in st.session_state:
    st.session_state['reactivate_selected_btn'] = 'left'

if 'user_email' not in st.session_state:
    st.session_state['user_email'] = ""
if 'business_id' not in st.session_state:
    st.session_state['business_id'] = ""
if 'business_details' not in st.session_state:
    st.session_state['business_details'] = {}
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = "Owner"
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

# NATIVE CSS OVERRIDES (STRICT LINK HOVER BLUE & BUTTON STYLING)
st.markdown("""
<style>
    /* 1. FORCE PURE BLUE LINK HOVER OVERRIDE */
    a, a:visited, a:link {
        color: #003366 !important;
        text-decoration: none !important;
        transition: color 0.2s ease-in-out !important;
    }
    a:hover, a:focus, a:active, p a:hover, span a:hover {
        color: #0000FF !important; /* Pure Vibrant Blue Hover */
        text-decoration: underline !important;
        font-weight: bold !important;
    }

    /* 2. PRIMARY BUTTONS */
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

    /* 3. SECONDARY BUTTONS */
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

# Country Codes Data
COUNTRY_DATA = {
    "🇵🇰 +92": {"code": "92", "placeholder": "300 1234567", "length": 10, "format_example": "+92 300 1234567"},
    "🇦🇪 +971": {"code": "971", "placeholder": "50 1234567", "length": 9, "format_example": "+971 50 1234567"},
    "🇸🇦 +966": {"code": "966", "placeholder": "50 1234567", "length": 9, "format_example": "+966 50 1234567"},
    "🇬🇧 +44": {"code": "44", "placeholder": "7911 123456", "length": 10, "format_example": "+44 7911 123456"},
    "🇺🇸 +1": {"code": "1", "placeholder": "201 555 0123", "length": 10, "format_example": "+1 201 555 0123"}
}

def mask_sensitive_text(text, role):
    if role == "Owner":
        return text
    if not text:
        return ""
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

def generate_username_suggestions(base_text):
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '', base_text.lower().replace(" ", "_"))
    if not cleaned:
        cleaned = "biz_ledger"
    suggestions = [f"{cleaned}_pk", f"{cleaned}_official", f"{cleaned}_store"]
    available = []
    for sug in suggestions:
        doc = db.collection('usernames').document(sug).get()
        if not doc.exists:
            available.append(sug)
        if len(available) >= 3:
            break
    return available

def purge_user_permanently(user_email, username, phone_raw):
    try:
        if user_email:
            db.collection('users').document(user_email).delete()
        if username:
            db.collection('usernames').document(username).delete()
        if phone_raw:
            db.collection('phone_numbers').document(phone_raw).delete()
        
        txs = db.collection('transactions').where('business_id', '==', user_email).stream()
        for t in txs:
            t.reference.delete()
            
        accs = db.collection('accountants').where('owner_email', '==', user_email).stream()
        for a in accs:
            a.reference.delete()
    except Exception:
        pass

def generate_excel_backup(user_data, user_email):
    output = io.BytesIO()
    tx_docs = db.collection('transactions').where('business_id', '==', user_email).stream()
    tx_list = [t.to_dict() for t in tx_docs]
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        profile_df = pd.DataFrame([{
            "Business Name": user_data.get("business_name", ""),
            "Username": user_data.get("username", ""),
            "Email": user_data.get("email", ""),
            "Phone": user_data.get("phone", ""),
            "Business Type": user_data.get("business_type", ""),
            "Export Date": get_current_time().strftime("%Y-%m-%d %H:%M:%S")
        }])
        profile_df.to_excel(writer, index=False, sheet_name='Account Profile')
        if tx_list:
            tx_df = pd.DataFrame(tx_list)
            if "logo_hex" in tx_df.columns:
                tx_df = tx_df.drop(columns=["logo_hex"])
            tx_df.to_excel(writer, index=False, sheet_name='Ledger Entries')
        else:
            pd.DataFrame([{"Message": "No transactions recorded yet."}]).to_excel(writer, index=False, sheet_name='Ledger Entries')
    return output.getvalue()

# Captcha Controls
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

# Dialogs & Popups
@st.dialog("⚠️ Business Account Alert")
def show_not_found_popup():
    st.error("🚨 Business Account Not Found!")
    st.write("No account exists with this Email, Username, or Phone Number. Please create a new account.")
    if st.button("👉 Go to Signup Window Now", type="primary", use_container_width=True):
        st.session_state['active_window'] = "Signup Window"
        st.rerun()

@st.dialog("🔄 Keep Account or Go Back?")
def show_reactivation_dialog():
    st.warning("⚠️ Pending Account Deletion Found!")
    st.write("Aapne is account ko **7 Days Deletion Queue** mein dala hua tha.")
    st.write("### **Kya aap apna account dobara rakhna chahte hain?**")
    
    col_r1, col_r2 = st.columns(2)
    r_left_type = "primary" if st.session_state['reactivate_selected_btn'] == 'left' else "secondary"
    r_right_type = "primary" if st.session_state['reactivate_selected_btn'] == 'right' else "secondary"

    with col_r1:
        if st.button("Submit", key="btn_reactivate_keep", type=r_left_type, use_container_width=True):
            st.session_state['reactivate_selected_btn'] = 'left'
            target_email = st.session_state['pending_login_data']['email']
            user_data = st.session_state['pending_login_data']['user_data']
            
            db.collection('users').document(target_email).update({
                "status": "active",
                "deletion_requested_at": firestore.DELETE_FIELD
            })
            user_data["status"] = "active"
            
            st.session_state['logged_in'] = True
            st.session_state['user_email'] = target_email
            st.session_state['business_id'] = target_email
            st.session_state['business_details'] = user_data
            st.session_state['user_role'] = "Owner"
            
            st.query_params["user"] = target_email
            st.query_params["role"] = "Owner"

            st.session_state['reactivate_prompt'] = False
            st.session_state['pending_login_data'] = {}
            st.toast("🎉 Welcome back! Your account has been re-activated.")
            st.rerun()

    with col_r2:
        if st.button("Cancel", key="btn_reactivate_cancel", type=r_right_type, use_container_width=True):
            st.session_state['reactivate_selected_btn'] = 'right'
            st.session_state['reactivate_prompt'] = False
            st.session_state['pending_login_data'] = {}
            st.session_state['active_window'] = "Signup Window"
            st.rerun()

@st.dialog("🗑️ Permanently Delete Account")
def show_delete_account_dialog():
    user_data = st.session_state['business_details']
    
    if st.session_state['del_step'] == 1:
        st.error("⚠️ WARNING: THIS ACTION CANNOT BE UNDONE!")
        st.write("Are you sure you want to request permanent deletion of your business account and all associated ledger entries?")
        st.write("")
        
        col_d1, col_d2 = st.columns(2)
        left_type = "primary" if st.session_state['del_selected_btn'] == 'left' else "secondary"
        right_type = "primary" if st.session_state['del_selected_btn'] == 'right' else "secondary"

        with col_d1:
            if st.button("YES, I AM SURE", key="btn_del_sure", type=left_type, use_container_width=True):
                st.session_state['del_selected_btn'] = 'left'
                st.session_state['del_step'] = 2
                st.rerun()
            
        with col_d2:
            if st.button("Cancel", key="btn_del_cancel", type=right_type, use_container_width=True):
                st.session_state['del_selected_btn'] = 'right'
                st.session_state['show_delete_dialog'] = False
                st.session_state['del_step'] = 1
                st.rerun()

    elif st.session_state['del_step'] == 2:
        st.subheader("🔐 Verify Account Ownership")
        st.write("Please enter your account details and password to confirm deletion request:")
        dn1, dn2, dans = get_locked_captcha("delete_acc")
        
        with st.form("delete_verify_form"):
            del_id = st.text_input("Enter Email, Username, or Phone Number *", value=st.session_state['user_email'])
            del_password = st.text_input("Enter Account Password *", type="password")
            del_captcha = st.text_input(f"Question: What is {dn1} + {dn2} ? *")
            submit_del_verify = st.form_submit_button("Submit", use_container_width=True)

        if submit_del_verify:
            if not del_id or not del_password or not del_captcha:
                st.warning("⚠️ Please fill in all verification fields.")
            elif not del_captcha.isnumeric() or int(del_captcha) != dans:
                refresh_locked_captcha("delete_acc")
                st.error("🚨 Incorrect Captcha answer!")
            else:
                if user_data.get('password') == make_hash(del_password):
                    st.session_state['del_step'] = 3
                    refresh_locked_captcha("delete_acc")
                    st.rerun()
                else:
                    st.error("🚨 Incorrect Password! Deletion aborted.")

    elif st.session_state['del_step'] == 3:
        st.warning("⏰ Account Deletion Scheduled in 7 Days!")
        st.write("Aapka account **7 Days** ke baad database se **permanently delete** kar diya jayega.")
        
        st.subheader("📊 Download Complete Data Backup (Excel File)")
        excel_backup_bytes = generate_excel_backup(user_data, st.session_state['user_email'])
        
        st.download_button(
            label="⬇️ Download Account Data File (.xlsx)",
            data=excel_backup_bytes,
            file_name=f"{user_data.get('username', 'user')}_ledger_backup.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.divider()
        if st.button("Submit", key="btn_del_final_submit", type="primary", use_container_width=True):
            now_iso = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
            db.collection('users').document(st.session_state['user_email']).update({
                "status": "deletion_requested",
                "deletion_requested_at": now_iso
            })
            
            st.session_state['logged_in'] = False
            st.session_state['user_email'] = ""
            st.session_state['business_id'] = ""
            st.session_state['business_details'] = {}
            st.session_state['user_role'] = "Owner"
            st.session_state['active_window'] = "Login Window"
            st.session_state['del_step'] = 1
            st.session_state['show_delete_dialog'] = False
            st.query_params.clear()
            st.rerun()

if st.session_state.get('show_delete_dialog', False):
    show_delete_account_dialog()

# ------------------ MAIN SCREEN: LOGIN & SIGNUP ------------------
if not st.session_state['logged_in']:
    st.title("💼 Asif Ledger Solutions - PC Edition")
    st.caption("Multi-Tenant Cloud Accounting & Ledger Platform")
    
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

    if st.session_state['reactivate_prompt']:
        show_reactivation_dialog()

    # ---------------- LOGIN WINDOW ----------------
    if st.session_state['active_window'] == "Login Window":
        st.markdown("### 🔑 Client & Team Account Login")
        
        saved_dict = st.session_state['saved_accounts_dict']
        selected_acc_key = "-- Select Saved Account --"
        if saved_dict:
            selected_acc_key = st.selectbox("💡 Quick Select Saved Account:", ["-- Select Saved Account --"] + list(saved_dict.keys()))
        
        preset_login = ""
        preset_password = ""
        if selected_acc_key != "-- Select Saved Account --":
            preset_login = saved_dict[selected_acc_key]["login"]
            preset_password = saved_dict[selected_acc_key]["password"]

        login_id_live = st.text_input("Username (@handle), Email, or Phone Number", value=preset_login, placeholder="e.g. user_handle, name@email.com, or +923001234567", key="login_id_live_key")
        
        is_login_disabled = False
        login_clean_check = login_id_live.strip()

        if login_clean_check:
            account_found = False
            if "@" in login_clean_check:
                if db.collection('users').document(login_clean_check.lower()).get().exists:
                    account_found = True
            else:
                digits = re.sub(r'\D', '', login_clean_check)
                if len(digits) >= 7:
                    phone_docs = db.collection('phone_numbers').stream()
                    for p_doc in phone_docs:
                        if digits in re.sub(r'\D', '', p_doc.id):
                            account_found = True
                            break
                if not account_found:
                    if db.collection('usernames').document(login_clean_check.lower()).get().exists:
                        account_found = True
                if not account_found:
                    acc_check = db.collection('accountants').where('username', '==', login_clean_check.lower()).stream()
                    if len(list(acc_check)) > 0:
                        account_found = True

            if not account_found:
                is_login_disabled = True
                st.error("🚨 ACCOUNT NOT FOUND! No registered account matches this entry.")
                st.info("👉 Since this account does not exist, please go to the Signup Window to create a new one.")
                if st.button("📝 Click Here to Go to Signup Window", type="primary", use_container_width=True):
                    st.session_state['active_window'] = "Signup Window"
                    st.rerun()

        l_n1, l_n2, l_ans = get_locked_captcha("login")

        with st.form("login_form", clear_on_submit=False):
            login_password = st.text_input("Password", type="password", value=preset_password, disabled=is_login_disabled)

            st.markdown("#### 🤖 Human Verification")
            login_captcha = st.text_input(f"Question: What is {l_n1} + {l_n2} ? *", placeholder="Enter sum answer", disabled=is_login_disabled)

            submit_login = st.form_submit_button("Submit", disabled=is_login_disabled)

        if submit_login and not is_login_disabled:
            val_id = str(login_id_live).strip()
            val_pw = str(login_password).strip()
            val_cap = str(login_captcha).strip()

            if not val_id or not val_pw or not val_cap:
                st.warning("⚠️ Please fill in all login fields and captcha before submitting.")
            elif not val_cap.isnumeric() or int(val_cap) != l_ans:
                refresh_locked_captcha("login")
                st.error("🚨 Incorrect Captcha answer!")
            else:
                login_clean = val_id
                target_email = ""
                user_role = "Owner"
                
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

                user_doc = db.collection('users').document(target_email).get()
                
                if not user_doc.exists:
                    acc_query = db.collection('accountants').where('username', '==', login_clean.lower()).stream()
                    for acc in acc_query:
                        acc_data = acc.to_dict()
                        if acc_data['password'] == make_hash(val_pw):
                            target_email = acc_data['owner_email']
                            user_doc = db.collection('users').document(target_email).get()
                            user_role = "Accountant"
                            break

                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    valid_pass = False
                    
                    if user_role == "Owner" and user_data['password'] == make_hash(val_pw):
                        valid_pass = True
                    elif user_role == "Accountant":
                        valid_pass = True

                    if valid_pass:
                        if user_data.get("status") == "deletion_requested" and user_role == "Owner":
                            req_time_str = user_data.get("deletion_requested_at")
                            if req_time_str:
                                req_dt = datetime.strptime(req_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo('Asia/Karachi'))
                                time_passed = get_current_time() - req_dt
                                
                                if time_passed > timedelta(days=7):
                                    purge_user_permanently(target_email, user_data.get("username"), user_data.get("phone_raw"))
                                    st.error("🚨 This account was permanently deleted after 7 days.")
                                    st.stop()
                                else:
                                    st.session_state['pending_login_data'] = {
                                        "email": target_email,
                                        "user_data": user_data,
                                        "password": val_pw
                                    }
                                    st.session_state['reactivate_prompt'] = True
                                    refresh_locked_captcha("login")
                                    st.rerun()

                        st.session_state['logged_in'] = True
                        st.session_state['user_email'] = target_email
                        st.session_state['business_id'] = target_email
                        st.session_state['business_details'] = user_data
                        st.session_state['user_role'] = user_role
                        
                        st.query_params["user"] = target_email
                        st.query_params["role"] = user_role
                        
                        account_label = f"{user_data.get('business_name', 'Business')} (@{user_data.get('username', 'user')})"
                        st.session_state['saved_accounts_dict'][account_label] = {
                            "login": target_email,
                            "password": val_pw
                        }
                        refresh_locked_captcha("login")
                        st.rerun()
                    else:
                        st.error("🚨 Incorrect Password! Please try again.")
                else:
                    show_not_found_popup()

    # ---------------- SIGNUP WINDOW ----------------
    elif st.session_state['active_window'] == "Signup Window":
        if st.session_state['otp_step']:
            st.markdown("### 🔐 Verify OTP Security Code")
            st.info(f"An OTP Verification code was dispatched for **{st.session_state['pending_user_data']['email']}**.")
            st.success(f"🔑 Secret OTP Code: **{st.session_state['generated_otp']}**")
            
            with st.form("otp_form"):
                entered_otp = st.text_input("Enter 6-Digit OTP Code:", max_chars=6)
                submit_otp = st.form_submit_button("Submit")

            if submit_otp:
                otp_val = str(entered_otp).strip()
                if otp_val == st.session_state['generated_otp']:
                    data = st.session_state['pending_user_data']
                    
                    db.collection('users').document(data['email']).set(data)
                    db.collection('usernames').document(data['username']).set({"email": data['email']})
                    db.collection('phone_numbers').document(data['phone_raw']).set({"email": data['email']})
                    
                    st.session_state['logged_in'] = True
                    st.session_state['user_email'] = data['email']
                    st.session_state['business_id'] = data['email']
                    st.session_state['business_details'] = data
                    st.session_state['user_role'] = "Owner"
                    
                    st.query_params["user"] = data['email']
                    st.query_params["role"] = "Owner"
                    
                    st.session_state['otp_step'] = False
                    st.session_state['generated_otp'] = ""
                    st.session_state['pending_user_data'] = {}
                    st.rerun()
                else:
                    st.error("❌ Invalid OTP Code. Please re-check and enter again.")

            st.markdown("---")
            if st.button("👉 Go to Login Window", type="primary"):
                st.session_state['active_window'] = "Login Window"
                st.rerun()

        else:
            st.markdown("### 📝 Create New Business Account (Owner)")
            
            check_email = st.text_input("User Email Address *", placeholder="name@domain.com", key="live_signup_email")
            email_clean = check_email.lower().strip()
            
            st.markdown("#### 📞 Contact Phone Number *")
            p_col1, p_col2 = st.columns([1.2, 2.8])
            with p_col1:
                selected_country = st.selectbox("Country Code", list(COUNTRY_DATA.keys()), key="live_country_select")
            
            country_info = COUNTRY_DATA[selected_country]
            
            with p_col2:
                check_phone = st.text_input(
                    f"Phone Number (Max {country_info['length']} digits)",
                    placeholder=country_info["placeholder"],
                    key=f"phone_input_{selected_country}"
                )

            phone_clean = re.sub(r'\D', '', check_phone)
            extracted_code = country_info["code"]
            formatted_phone_key = f"+{extracted_code}_{phone_clean}"

            is_signup_disabled = False
            
            if email_clean and db.collection('users').document(email_clean).get().exists:
                is_signup_disabled = True
                st.error("🚨 THIS EMAIL IS ALREADY REGISTERED!")
                st.info("👉 An account with this email already exists. Click below to go to the Login Window.")
                if st.button("🔑 Click Here to Go to Login Window", type="primary", use_container_width=True):
                    st.session_state['active_window'] = "Login Window"
                    st.rerun()

            elif phone_clean and len(phone_clean) == country_info['length'] and db.collection('phone_numbers').document(formatted_phone_key).get().exists:
                is_signup_disabled = True
                st.error("🚨 THIS PHONE NUMBER IS ALREADY REGISTERED!")
                st.info("👉 An account with this phone number already exists. Click below to go to the Login Window.")
                if st.button("🔑 Click Here to Go to Login Window", type="primary", use_container_width=True):
                    st.session_state['active_window'] = "Login Window"
                    st.rerun()

            s_n1, s_n2, s_ans = get_locked_captcha("signup")

            with st.form("signup_form"):
                grid_c1, grid_c2 = st.columns(2)
                with grid_c1:
                    password = st.text_input("Unique Password *", type="password", placeholder="8+ chars, Uppercase, Number & Symbol", disabled=is_signup_disabled)
                    biz_name = st.text_input("Business Name *", placeholder="e.g. Ali Traders, Bismillah Pharmacy", disabled=is_signup_disabled)

                with grid_c2:
                    username_input = st.text_input("Choose Unique Username / Handle (Optional)", placeholder="Auto-generated if left empty", disabled=is_signup_disabled)
                    biz_type = st.selectbox("Business Category", ["Grocery Store", "Medical Store / Pharmacy", "General Store", "Services / Consulting", "Wholesale", "Other"], disabled=is_signup_disabled)

                st.markdown("#### 🤖 Human Verification")
                captcha_input = st.text_input(f"Question: What is {s_n1} + {s_n2} ? *", placeholder="Enter sum answer", disabled=is_signup_disabled)
                logo_file = st.file_uploader("Upload Business Logo (PNG / JPG)", type=["png", "jpg", "jpeg"], disabled=is_signup_disabled)

                submit_signup = st.form_submit_button("Submit", disabled=is_signup_disabled)

            if submit_signup and not is_signup_disabled:
                if not email_clean or not password or not biz_name or not phone_clean or not captcha_input:
                    st.warning("⚠️ Please fill in all required fields (*).")
                elif not validate_email_format(email_clean):
                    st.error("🚨 Invalid Email Address format!")
                elif len(phone_clean) != country_info['length']:
                    st.error(f"🚨 Phone number must be exactly {country_info['length']} digits for {selected_country}.")
                else:
                    is_pw_strong, pw_msg = validate_password_strength(password)
                    if not is_pw_strong:
                        st.error(f"🚨 Weak Password! {pw_msg}")
                    elif len(biz_name.strip()) < 3 or biz_name.strip().isnumeric():
                        st.error("🚨 Please enter a valid Business Name (at least 3 characters).")
                    elif not str(captcha_input).strip().isnumeric() or int(captcha_input) != s_ans:
                        refresh_locked_captcha("signup")
                        st.error("🚨 Incorrect Captcha answer!")
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
                            "status": "active",
                            "created_at": get_current_time().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        st.session_state['generated_otp'] = generated_code
                        st.session_state['otp_step'] = True
                        refresh_locked_captcha("signup")
                        st.rerun()

# ------------------ DASHBOARD VIEW ------------------
else:
    biz_info = st.session_state['business_details']
    role = st.session_state['user_role']
    
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
        st.caption(f"Role: **{role}** | Category: {biz_info.get('business_type', 'General')} | Handle: @{biz_info.get('username', 'business')} | Contact: {mask_sensitive_text(biz_info.get('phone', ''), role)}")

    with top_c3:
        if st.button("🚪 Logout", type="secondary"):
            st.session_state['logged_in'] = False
            st.session_state['user_email'] = ""
            st.session_state['business_id'] = ""
            st.session_state['business_details'] = {}
            st.session_state['user_role'] = "Owner"
            st.session_state['active_window'] = "Login Window"
            st.session_state['otp_step'] = False
            st.query_params.clear()
            st.rerun()

    st.divider()

    # CATEGORY AUTOMATION
    CATEGORIES = {
        "Fuel & Automobile": ["shell", "pso", "total", "petrol", "fuel", "cng"],
        "Utilities": ["k-electric", "lesco", "fesco", "ptcl", "stormfiber", "sngpl", "bill"],
        "Groceries & Food": ["metro", "carrefour", "chaseup", "kfc", "mcdonalds", "foodpanda"],
        "Software & Services": ["google", "netflix", "openai", "aws", "github"],
        "Bank & Transfer Fees": ["fee", "tax", "charge", "atm fee"]
    }

    def auto_assign_category(merchant_name, sms_text):
        text = (str(merchant_name) + " " + str(sms_text)).lower()
        for category, keywords in CATEGORIES.items():
            if any(keyword in text for keyword in keywords):
                return category
        return "General Expense"

    # STRICT PARSER: RUPEES VS DATE SAFEGUARD & MERCHANT NAME FIX
    def parse_sms_logic(sms_text, custom_merchant_name=""):
        # Explicit Regex matching Currency terms (Rs, PKR, INR, $) to avoid picking up dates
        amount_match = re.search(r'(?:Rs\.?|INR|PKR|\$)\s*([\d,]+(?:\.\d{1,2})?)', sms_text, re.IGNORECASE)
        
        if amount_match:
            amount = float(amount_match.group(1).replace(',', ''))
        else:
            # Fallback for plain numeric values while ignoring full date formats (YYYY-MM-DD or DD/MM/YYYY)
            clean_text_no_dates = re.sub(r'\b\d{2,4}[-/\.]\d{1,2}[-/\.]\d{2,4}\b', '', sms_text)
            nums = re.findall(r'\b\d+(?:\.\d{1,2})?\b', clean_text_no_dates)
            amount = float(nums[0]) if nums else 0.0

        # Merchant fallback priority: Form Input -> Regex Extraction -> Default Name
        merchant = custom_merchant_name.strip() if custom_merchant_name.strip() else ""
        if not merchant:
            merchant_match = re.search(r'(?:to|at|paid to|sent to|received from|from|transfer from)\s+([A-Za-z0-9\s&]+?)(?=\s+(?:via|on|from|ref|dated|code|\.|$))', sms_text, re.IGNORECASE)
            if merchant_match:
                merchant = merchant_match.group(1).strip()

        if not merchant:
            merchant = "Direct Customer / Merchant"

        method_match = re.search(r'(?:via|using|through)\s+([A-Za-z0-9\s]+?)(?=\s+(?:on|dated|ref|\.|$))', sms_text, re.IGNORECASE)
        payment_method = method_match.group(1).strip() if method_match else "Cash / Direct"

        is_debit = any(word in sms_text.lower() for word in ["paid", "sent", "debited", "spent", "withdrawn"])
        cat = auto_assign_category(merchant, sms_text) if is_debit else "Income"

        return {
            "business_id": st.session_state['business_id'],
            "entered_by_role": role,
            "raw_sms": sms_text,
            "amount": amount,
            "merchant": merchant,
            "payment_method": payment_method,
            "type": "Debit" if is_debit else "Credit",
            "category": cat,
            "status": "processed",
            "timestamp": get_current_time().strftime("%Y-%m-%d %H:%M:%S")
        }

    st.sidebar.header("📩 Add Live Transaction / SMS")
    with st.sidebar.form("add_entry_form"):
        merchant_input = st.text_input("Customer / Party Name *", placeholder="e.g. Ali Traders, Kashif")
        user_sms = st.text_area("Paste SMS / Payment Note *", placeholder="e.g. Received Rs 5,000 via EasyPaisa or Paid Rs 2500")
        current_now = get_current_time()
        custom_date = st.date_input("Transaction Date:", value=current_now.date())
        custom_time = st.time_input("Transaction Time:", value=current_now.time())
        
        submit_entry = st.form_submit_button("Submit")

    if submit_entry:
        if user_sms.strip():
            entry_timestamp = datetime.combine(custom_date, custom_time).strftime("%Y-%m-%d %H:%M:%S")
            parsed_record = parse_sms_logic(user_sms, merchant_input)
            parsed_record["timestamp"] = entry_timestamp
            
            db.collection('transactions').add(parsed_record)
            st.sidebar.success("✅ Transaction Saved Successfully!")
            st.rerun()
        else:
            st.sidebar.warning("⚠️ Please enter SMS or transaction details.")

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

    # DYNAMIC TABS FOR OWNER VS ACCOUNTANT
    if role == "Owner":
        tab_dashboard, tab_accounts, tab_customers, tab_team = st.tabs([
            "📊 Main Ledger Dashboard", 
            "📚 Chart of Accounts", 
            "👥 Customer Directory & Statements",
            "🛡️ Team Management (RBAC)"
        ])
    else:
        tab_dashboard, tab_accounts, tab_customers = st.tabs([
            "📊 Main Ledger Dashboard", 
            "📚 Chart of Accounts", 
            "👥 Customer Directory & Statements"
        ])

    # 1. MAIN LEDGER DASHBOARD TAB
    with tab_dashboard:
        if not df.empty:
            st.sidebar.divider()
            st.sidebar.header("🔍 Filters & Options")
            
            all_categories = ["All"] + list(df['category'].dropna().unique())
            selected_category = st.sidebar.selectbox("Filter by Category:", all_categories)
            selected_type = st.sidebar.radio("Transaction Type:", ["All", "Debit (Expense)", "Credit (Income)"])

            filtered_df = df.copy()
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
            
            # TRANSACTIONS GRAPH IN DIFFERENT COLORS (RED/GREEN)
            st.subheader("📈 Transactions Summary Graph")
            chart_data = filtered_df.groupby(['type'])['amount'].sum().reset_index()
            if not chart_data.empty:
                st.bar_chart(data=chart_data, x='type', y='amount', color='type')

            st.divider()
            st.subheader("📋 Ledger Transactions Records")
            display_df = filtered_df.copy()
            display_df['Date & Time'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
            
            if 'entered_by_role' not in display_df.columns:
                display_df['entered_by_role'] = 'Owner'

            st.dataframe(
                display_df[['Date & Time', 'amount', 'merchant', 'category', 'type', 'payment_method', 'entered_by_role', 'status']],
                width='stretch'
            )
        else:
            st.info("💡 No transactions recorded yet. Use the **Add Live Transaction** form in the sidebar to add your first entry!")

    # 2. CHART OF ACCOUNTS TAB
    with tab_accounts:
        st.subheader("📚 Chart of Accounts")
        if not df.empty:
            cat_summary = df.groupby(['category', 'type'])['amount'].sum().reset_index()
            cat_summary.columns = ['Account Category', 'Type', 'Total Balance (Rs.)']
            st.dataframe(cat_summary, width='stretch')
        else:
            st.info("Chart of accounts will automatically populate when transactions are recorded.")

    # 3. CUSTOMER DIRECTORY TAB
    with tab_customers:
        st.subheader("👥 Customer & Merchant Directory")
        if not df.empty:
            merchants_list = sorted(list(df['merchant'].unique()))
            selected_merchant = st.selectbox("Select Customer / Merchant:", merchants_list)
            if selected_merchant:
                m_df = df[df['merchant'] == selected_merchant]
                st.dataframe(m_df[['timestamp', 'amount', 'type', 'category', 'raw_sms']], width='stretch')
        else:
            st.info("Customer history will appear here once entries are recorded.")

    # 4. TEAM MANAGEMENT TAB (ONLY OWNER ACCESS)
    if role == "Owner":
        with tab_team:
            st.subheader("👥 Accountant Team Management (Max 2 Allowed)")
            st.info("Assign Accountants restricted access to add/view ledger entries without seeing private account options.")
            
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
                        st.warning("Please fill in all fields.")
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

    # BOTTOM SECURITY & DELETE ZONE (EXCLUSIVELY RESTRICTED TO OWNER ONLY)
    st.markdown("---")
    bot_col1, bot_col2 = st.columns([3, 1])
    with bot_col1:
        st.caption(f"🔒 Security & Data Privacy Zone | Current Role: **{role}**")
    with bot_col2:
        # STRICT CONDITION: SHOW DELETE BUTTON ONLY TO OWNER
        if role == "Owner":
            if st.button("🗑️ Delete Account", type="primary", use_container_width=True):
                st.session_state['del_selected_btn'] = 'left'
                st.session_state['del_step'] = 1
                st.session_state['show_delete_dialog'] = True
                st.rerun()