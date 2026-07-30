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
st.set_page_config(page_title="Asif Ledger Solutions", layout="wide")

# Custom CSS: Button Color Overrides (Blue vs Black Rules)
st.markdown("""
<style>
    /* 1. Standard Primary & Login Buttons (Blue Override) */
    button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"],
    div.stButton > button[kind="primary"],
    .blue-btn button,
    div.blue-btn > button {
        background-color: #003366 !important;
        color: #ffffff !important;
        border-color: #002244 !important;
        background-image: none !important;
        font-weight: bold !important;
    }

    button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover,
    div.stButton > button[kind="primary"]:hover,
    .blue-btn button:hover,
    div.blue-btn > button:hover {
        background-color: #0056b3 !important;
        color: #ffffff !important;
        border-color: #004085 !important;
        cursor: pointer !important;
    }

    /* 2. Delete Account Specific Buttons (Black Override) */
    .delete-btn-black button,
    div.delete-btn-black > button,
    button[data-testid="baseButton-delete"] {
        background-color: #1e1e1e !important;
        color: #ffffff !important;
        border: 1px solid #000000 !important;
        font-weight: bold !important;
    }
    .delete-btn-black button:hover,
    div.delete-btn-black > button:hover {
        background-color: #333333 !important;
        color: #ffffff !important;
        border-color: #000000 !important;
        cursor: pointer !important;
    }

    /* 3. Neutral Secondary Buttons */
    button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"],
    div.stButton > button[kind="secondary"] {
        background-color: #f0f2f6 !important;
        color: #333333 !important;
        border: 1px solid #cccccc !important;
    }

    button[kind="secondary"]:hover,
    .stButton > button[data-testid="baseButton-secondary"]:hover,
    div.stButton > button[kind="secondary"]:hover {
        background-color: #e0e0e0 !important;
        color: #000000 !important;
        cursor: pointer !important;
    }

    /* Links & Typography */
    a {
        color: #003366 !important;
        text-decoration: none !important;
        transition: color 0.2s ease-in-out;
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

# Country Codes Data
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

# Permanent Purge Helper
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
    except Exception:
        pass

# Excel Backup Generator
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
if 'del_step' not in st.session_state:
    st.session_state['del_step'] = 1
if 'show_delete_dialog' not in st.session_state:
    st.session_state['show_delete_dialog'] = False
if 'reactivate_prompt' not in st.session_state:
    st.session_state['reactivate_prompt'] = False
if 'pending_login_data' not in st.session_state:
    st.session_state['pending_login_data'] = {}

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

# Dialogs
@st.dialog("⚠️ Business Account Alert")
def show_not_found_popup():
    st.error("🚨 Business Account Not Found!")
    st.write("No account exists with this Email, Username, or Phone Number. Please create a new account.")
    st.markdown('<div class="blue-btn">', unsafe_allow_html=True)
    if st.button("👉 Go to Signup Window Now", use_container_width=True):
        st.session_state['active_window'] = "Signup Window"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ------------------ RE-ACTIVATION DIALOG PROMPT (Keep Account = BLUE) ------------------
@st.dialog("🔄 Keep Account or Go Back?")
def show_reactivation_dialog():
    st.warning("⚠️ Pending Account Deletion Found!")
    st.write("Aapne is account ko **7 Days Deletion Queue** mein dala hua tha.")
    st.write("### **Kya aap apna account dobara rakhna chahte hain?**")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        # Re-activation / Keep Account Override to Blue
        st.markdown('<div class="blue-btn">', unsafe_allow_html=True)
        if st.button("✅ Yes, Keep My Account", use_container_width=True):
            target_email = st.session_state['pending_login_data']['email']
            user_data = st.session_state['pending_login_data']['user_data']
            val_pw = st.session_state['pending_login_data']['password']
            
            db.collection('users').document(target_email).update({
                "status": "active",
                "deletion_requested_at": firestore.DELETE_FIELD
            })
            user_data["status"] = "active"
            
            st.session_state['logged_in'] = True
            st.session_state['user_email'] = target_email
            st.session_state['business_id'] = target_email
            st.session_state['business_details'] = user_data
            
            account_label = f"{user_data.get('business_name', 'Business')} (@{user_data.get('username', 'user')})"
            st.session_state['saved_accounts_dict'][account_label] = {
                "login": target_email,
                "password": val_pw
            }
            
            st.session_state['reactivate_prompt'] = False
            st.session_state['pending_login_data'] = {}
            st.toast("🎉 Welcome back! Your account has been re-activated.")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col_r2:
        if st.button("🚫 Go Back to Signup", use_container_width=True):
            st.session_state['reactivate_prompt'] = False
            st.session_state['pending_login_data'] = {}
            st.session_state['active_window'] = "Signup Window"
            st.rerun()

# ------------------ DELETE ACCOUNT DIALOG (Black Buttons & Alignment Fixed) ------------------
@st.dialog("🗑️ Permanently Delete Account")
def show_delete_account_dialog():
    user_data = st.session_state['business_details']
    
    # Step 1: Alignment Fix & Instant Next Step Transition
    if st.session_state['del_step'] == 1:
        st.error("⚠️ WARNING: THIS ACTION CANNOT BE UNDONE!")
        st.write("Are you sure you want to request permanent deletion of your business account and all associated ledger entries?")
        st.write("")
        
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.markdown('<div class="delete-btn-black">', unsafe_allow_html=True)
            if st.button("YES, I AM SURE", key="btn_del_sure", use_container_width=True):
                st.session_state['del_step'] = 2
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col_d2:
            if st.button("Cancel", key="btn_del_cancel", use_container_width=True):
                st.session_state['show_delete_dialog'] = False
                st.session_state['del_step'] = 1
                st.rerun()

    # Step 2: Form & Verification
    elif st.session_state['del_step'] == 2:
        st.subheader("🔐 Verify Account Ownership")
        st.write("Please enter your account details and password to confirm deletion request:")
        
        dn1, dn2, dans = get_locked_captcha("delete_acc")
        
        with st.form("delete_verify_form"):
            del_id = st.text_input("Enter Email, Username, or Phone Number *", value=st.session_state['user_email'])
            del_password = st.text_input("Enter Account Password *", type="password")
            del_captcha = st.text_input(f"Question: What is {dn1} + {dn2} ? *")
            
            st.markdown('<div class="delete-btn-black">', unsafe_allow_html=True)
            submit_del_verify = st.form_submit_button("Verify Details & Proceed Deletion", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

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

    # Step 3: Excel File Backup & Confirmation
    elif st.session_state['del_step'] == 3:
        st.warning("⏰ Account Deletion Scheduled in 7 Days!")
        st.write("Aapka account **7 Days** (168 Hours) ke baad database se **permanently delete** kar diya jayega.")
        st.info("💡 **Note:** Is 7 Days ke doran agar aap login karenge toh aap se poocha jayega ke aap account rakhna chahte hain ya Signup par jana chahte hain.")
        
        st.subheader("📊 Download Complete Data Backup (Excel File)")
        st.write("Niche button se apna data Excel File (`.xlsx`) format mein download kar lein:")

        excel_backup_bytes = generate_excel_backup(user_data, st.session_state['user_email'])
        
        st.download_button(
            label="⬇️ Download Account Data File (.xlsx)",
            data=excel_backup_bytes,
            file_name=f"{user_data.get('username', 'user')}_ledger_backup.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.divider()
        st.markdown('<div class="delete-btn-black">', unsafe_allow_html=True)
        if st.button("Submit Deletion Request & Logout", use_container_width=True):
            now_iso = get_current_time().strftime("%Y-%m-%d %H:%M:%S")
            db.collection('users').document(st.session_state['user_email']).update({
                "status": "deletion_requested",
                "deletion_requested_at": now_iso
            })
            
            st.session_state['logged_in'] = False
            st.session_state['user_email'] = ""
            st.session_state['business_id'] = ""
            st.session_state['business_details'] = {}
            st.session_state['active_window'] = "Login Window"
            st.session_state['del_step'] = 1
            st.session_state['show_delete_dialog'] = False
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# Render Delete Dialog if Triggered
if st.session_state.get('show_delete_dialog', False):
    show_delete_account_dialog()

# ------------------ SCREEN 1: LOGIN & SIGNUP WINDOWS ------------------
if not st.session_state['logged_in']:
    st.title("💼 Asif Ledger Solutions")
    st.caption("Multi-Tenant Cloud Accounting & Ledger Platform")
    
    col_w1, col_w2, _ = st.columns([1, 1, 2])
    with col_w1:
        is_login = st.session_state['active_window'] == "Login Window"
        # Login Button UI Overridden to Blue
        st.markdown('<div class="blue-btn">' if is_login else '<div>', unsafe_allow_html=True)
        if st.button("🔑 Login", use_container_width=True, type="primary" if is_login else "secondary"):
            st.session_state['active_window'] = "Login Window"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col_w2:
        is_signup = st.session_state['active_window'] == "Signup Window"
        st.markdown('<div class="blue-btn">' if is_signup else '<div>', unsafe_allow_html=True)
        if st.button("📝 Signup", use_container_width=True, type="primary" if is_signup else "secondary"):
            st.session_state['active_window'] = "Signup Window"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    if st.session_state['reactivate_prompt']:
        show_reactivation_dialog()

    # WINDOW 1: LOGIN WINDOW
    if st.session_state['active_window'] == "Login Window":
        st.markdown("### 🔑 Client Account Login")
        
        saved_dict = st.session_state['saved_accounts_dict']
        selected_acc_key = "-- Select Saved Account --"
        
        if saved_dict:
            selected_acc_key = st.selectbox("💡 Quick Select Saved Account:", ["-- Select Saved Account --"] + list(saved_dict.keys()))
        
        preset_login = ""
        preset_password = ""
        
        if selected_acc_key != "-- Select Saved Account --":
            preset_login = saved_dict[selected_acc_key]["login"]
            preset_password = saved_dict[selected_acc_key]["password"]

        l_n1, l_n2, l_ans = get_locked_captcha("login")

        with st.form("login_form", clear_on_submit=False):
            login_id = st.text_input("Username (@handle), Email, or Phone Number", value=preset_login, placeholder="e.g. user_handle, name@email.com, or +923001234567")
            login_password = st.text_input("Password", type="password", value=preset_password)

            st.markdown("#### 🤖 Human Verification")
            login_captcha = st.text_input(f"Question: What is {l_n1} + {l_n2} ? *", placeholder="Enter sum answer")

            st.markdown('<div class="blue-btn">', unsafe_allow_html=True)
            submit_login = st.form_submit_button("🔑 Login to Dashboard", type="primary")
            st.markdown('</div>', unsafe_allow_html=True)

        if submit_login:
            val_id = str(login_id).strip()
            val_pw = str(login_password).strip()
            val_cap = str(login_captcha).strip()

            if not val_id or not val_pw or not val_cap:
                st.warning("⚠️ Please fill in all login fields and captcha before submitting.")
            elif not val_cap.isnumeric() or int(val_cap) != l_ans:
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
                            
                            # Check 7-Day Deletion Expiry & Re-Activation Prompt
                            if user_data.get("status") == "deletion_requested":
                                req_time_str = user_data.get("deletion_requested_at")
                                if req_time_str:
                                    req_dt = datetime.strptime(req_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo('Asia/Karachi'))
                                    time_passed = get_current_time() - req_dt
                                    
                                    if time_passed > timedelta(days=7):
                                        purge_user_permanently(target_email, user_data.get("username"), user_data.get("phone_raw"))
                                        st.error("🚨 This account was permanently deleted after 7 days as requested.")
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

                            # Login Successful
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
                            st.rerun()
                        else:
                            st.error("🚨 Incorrect Password! Please try again.")
                    else:
                        show_not_found_popup()
                else:
                    show_not_found_popup()

    # WINDOW 2: SIGNUP WINDOW
    elif st.session_state['active_window'] == "Signup Window":
        if st.session_state['otp_step']:
            st.markdown("### 🔐 Verify OTP Security Code")
            st.info(f"An OTP Verification code was dispatched for **{st.session_state['pending_user_data']['email']}**.")
            st.success(f"🔑 Secret OTP Code: **{st.session_state['generated_otp']}**")
            
            with st.form("otp_form"):
                entered_otp = st.text_input("Enter 6-Digit OTP Code:", max_chars=6)
                st.markdown('<div class="blue-btn">', unsafe_allow_html=True)
                submit_otp = st.form_submit_button("✅ Verify OTP & Finalize Account", type="primary")
                st.markdown('</div>', unsafe_allow_html=True)

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
                    
                    st.session_state['otp_step'] = False
                    st.session_state['generated_otp'] = ""
                    st.session_state['pending_user_data'] = {}
                    st.rerun()
                else:
                    st.error("❌ Invalid OTP Code. Please re-check and enter again.")

            st.markdown("---")
            st.markdown('<div class="blue-btn">', unsafe_allow_html=True)
            if st.button("👉 Go to Login Window"):
                st.session_state['active_window'] = "Login Window"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        else:
            st.markdown("### 📝 Create New Business Account")
            s_n1, s_n2, s_ans = get_locked_captcha("signup")

            with st.form("signup_form"):
                check_email = st.text_input("User Email Address *", placeholder="name@domain.com")
                
                st.markdown("#### 📞 Contact Phone Number *")
                p_col1, p_col2 = st.columns([1, 3])
                with p_col1:
                    selected_country = st.selectbox("Country Code", list(COUNTRY_DATA.keys()))
                
                country_info = COUNTRY_DATA[selected_country]
                
                with p_col2:
                    check_phone = st.text_input("Phone Number", placeholder=country_info["placeholder"])

                grid_c1, grid_c2 = st.columns(2)
                with grid_c1:
                    password = st.text_input("Unique Password *", type="password", placeholder="8+ chars, Uppercase, Number & Symbol")
                    biz_name = st.text_input("Business Name *", placeholder="e.g. Ali Traders, Bismillah Pharmacy")

                with grid_c2:
                    username_input = st.text_input("Choose Unique Username / Handle (Optional)", placeholder="Auto-generated if left empty")
                    biz_type = st.selectbox("Business Category", ["Grocery Store", "Medical Store / Pharmacy", "General Store", "Services / Consulting", "Wholesale", "Other"])

                st.markdown("#### 🤖 Human Verification")
                captcha_input = st.text_input(f"Question: What is {s_n1} + {s_n2} ? *", placeholder="Enter sum answer")
                logo_file = st.file_uploader("Upload Business Logo (PNG / JPG)", type=["png", "jpg", "jpeg"])

                st.markdown('<div class="blue-btn">', unsafe_allow_html=True)
                submit_signup = st.form_submit_button("🚀 Verify & Create Account", type="primary")
                st.markdown('</div>', unsafe_allow_html=True)

            if submit_signup:
                email_clean = check_email.lower().strip()
                phone_clean = re.sub(r'\D', '', check_phone)
                extracted_code = country_info["code"]
                formatted_phone_key = f"+{extracted_code}_{phone_clean}"

                if not email_clean or not password or not biz_name or not phone_clean or not captcha_input:
                    st.warning("⚠️ Please fill in all required fields (*).")
                elif not validate_email_format(email_clean):
                    st.error("🚨 Invalid Email Address format!")
                elif db.collection('users').document(email_clean).get().exists:
                    st.error("🚨 This Email is already registered!")
                elif db.collection('phone_numbers').document(formatted_phone_key).get().exists:
                    st.error("🚨 This Phone Number is already registered!")
                else:
                    is_pw_strong, pw_msg = validate_password_strength(password)
                    if not is_pw_strong:
                        st.error(f"🚨 Weak Password! {pw_msg}")
                    elif len(biz_name.strip()) < 3 or biz_name.strip().isnumeric():
                        st.error("🚨 Please enter a valid Business Name (at least 3 characters).")
                    elif not str(captcha_input).strip().isnumeric() or int(captcha_input) != s_ans:
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
                            "status": "active",
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
        if st.button("🚪 Logout"):
            st.session_state['logged_in'] = False
            st.session_state['user_email'] = ""
            st.session_state['business_id'] = ""
            st.session_state['business_details'] = {}
            st.session_state['active_window'] = "Login Window"
            st.session_state['otp_step'] = False
            st.rerun()

    st.divider()

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

    tab_dashboard, tab_accounts, tab_customers = st.tabs(["📊 Main Ledger Dashboard", "📚 Chart of Accounts", "👥 Customer Directory & Statements"])

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

    # Sidebar Live SMS Entry
    st.sidebar.header("📩 Add Live SMS Transaction")
    user_sms = st.sidebar.text_area("Paste SMS Text Here:", placeholder="Received Rs 5,000 from Ali Traders via EasyPaisa.")
    
    current_now = get_current_time()
    custom_date = st.sidebar.date_input("Transaction Date:", value=current_now.date())
    custom_time = st.sidebar.time_input("Transaction Time:", value=current_now.time())
    entry_timestamp = datetime.combine(custom_date, custom_time).strftime("%Y-%m-%d %H:%M:%S")

    st.sidebar.markdown('<div class="blue-btn">', unsafe_allow_html=True)
    if st.sidebar.button("Process & Save Transaction", type="primary"):
        if user_sms.strip():
            parsed_record = parse_sms_logic(user_sms)
            parsed_record["timestamp"] = entry_timestamp
            
            db.collection('transactions').add(parsed_record)
            st.sidebar.success("✅ Transaction Saved for Your Business!")
            st.rerun()
        else:
            st.sidebar.warning("Please enter an SMS first.")
    st.sidebar.markdown('</div>', unsafe_allow_html=True)

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

    with tab_accounts:
        st.subheader("📚 Chart of Accounts")
        st.write("Overview of automatically mapped Income, Expense, and Asset accounts.")
        
        if not df.empty:
            cat_summary = df.groupby(['category', 'type'])['amount'].sum().reset_index()
            cat_summary.columns = ['Account Name / Category', 'Account Type', 'Total Balance (Rs.)']
            st.dataframe(cat_summary, width='stretch')
        else:
            st.info("Chart of accounts will generate automatically as soon as entries are recorded.")

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

    # ------------------ BOTTOM DELETE USER SECTION (Black Color Trigger) ------------------
    st.markdown("---")
    bot_col1, bot_col2 = st.columns([3, 1])
    with bot_col1:
        st.caption("🔒 Security & Data Privacy Zone")
    with bot_col2:
        st.markdown('<div class="delete-btn-black">', unsafe_allow_html=True)
        if st.button("🗑️ Delete Account", use_container_width=True):
            st.session_state['del_step'] = 1
            st.session_state['show_delete_dialog'] = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)