import streamlit as st
import pandas as pd
import random
from datetime import datetime, timedelta, date
import matplotlib.pyplot as plt
import os
import requests

from openpyxl.workbook import Workbook
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# --- FILE STORAGE ---
FILE_PATH = "food_posts_100.xlsx"
ACCOUNTS_FILE = "accounts.xlsx"

if os.path.exists(FILE_PATH):
    df = pd.read_excel(FILE_PATH)
else:
    df = pd.DataFrame(columns=["id", "restaurant", "food_item", "quantity",
                               "location", "expiry_time", "status", "claimed_by"])
    df.to_excel(FILE_PATH, index=False)

def save_food_db():
    df.to_excel(FILE_PATH, index=False)

# --- PAGE CONFIG ---
st.set_page_config(page_title="Food Rescue Network", page_icon="🥗", layout="centered")

#---background---
page_bg_img = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("https://plus.unsplash.com//premium_photo-1674106347537-f0b19d647413?q=80&w=1170&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D");
    background-size: cover;
    background-repeat: no-repeat;
    background-attachment: fixed;
}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)


#---ACCOUNTS DATABASE---
if os.path.exists(ACCOUNTS_FILE):
    accounts_df = pd.read_excel(ACCOUNTS_FILE)
else:
    accounts_df = pd.DataFrame(columns=[
        "name","email","password","phone","organization","role"
    ])
    accounts_df.to_excel(ACCOUNTS_FILE, index=False)

def save_accounts_db():
    accounts_df.to_excel(ACCOUNTS_FILE, index=False)

# --- SESSION STATE ---
if "stage" not in st.session_state:
    st.session_state.stage = "role"
if "user_data" not in st.session_state:
    st.session_state.user_data = {}
if "otp" not in st.session_state:
    st.session_state.otp = None
if "otp_verified" not in st.session_state:
    st.session_state.otp_verified = False
if "accounts" not in st.session_state:
    st.session_state.accounts = {row["email"]: row.to_dict() for _,row in accounts_df.iterrows()}

# --- PRE-DEFINED ADMIN ACCOUNT ---
ADMIN_EMAIL = "admin@foodrescue.com"
ADMIN_PASS = "admin123"
if ADMIN_EMAIL not in st.session_state.accounts:
    admin_row = {
        "name": "System Admin",
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASS,
        "phone": "N/A",
        "organization": "Food Rescue Network",
        "role": "Admin"
    }
    accounts_df.loc[len(accounts_df)]=admin_row
    save_accounts_db()
    st.session_state.accounts[ADMIN_EMAIL] = admin_row

# --- LOGOUT ---
def logout():
    st.session_state.stage = "role"
    st.session_state.user_data = {}
    st.session_state.otp_verified = False
    st.rerun()

# --- DASHBOARD HEADER ---
def dashboard_header(title):
    col1, col2 = st.columns([8, 1])
    col1.markdown(f"### {title}")
    if col2.button("Logout"):
        logout()

# --- REAL OTP SECTION ---
def send_otp_via_phone(phone, otp):
    """Send OTP via Twilio SMS"""
    try:
        client = Client(st.secrets["TWILIO_SID"], st.secrets["TWILIO_AUTH"])
        verification = client.verify.services(st.secrets["TWILIO_SERVICE_SID"]) \
            .verifications.create(to=phone, channel="sms")
        st.success(f"📱 OTP sent to {phone}")
    except Exception as e:
        st.error(f"Failed to send OTP via phone: {e}")

def send_otp_via_email(email, otp):
    """Send OTP via SendGrid Email"""
    try:
        message = Mail(
            from_email=st.secrets["FROM_EMAIL"],
            to_emails=email,
            subject="Your OTP Code",
            plain_text_content=f"Your OTP is: {otp}"
        )
        sg = SendGridAPIClient(st.secrets["SENDGRID_API_KEY"])
        response = sg.send(message)
        if response.status_code in [200, 202]:
            st.success(f"📧 OTP sent to {email}")
        else:
            st.error(f"SendGrid failed: {response.status_code}")
    except Exception as e:
        st.error(f"Failed to send OTP via email: {e}")

def otp_verification_flow():
    st.subheader("🔐 OTP Verification")
    otp_choice = st.radio("Receive OTP via:", ["Email", "Phone"])
    if st.button("Send OTP"):
        otp = str(random.randint(1000, 9999))
        st.session_state.otp = otp
        if otp_choice == "Email":
            send_otp_via_email(st.session_state.user_data["email"], otp)
        else:
            send_otp_via_phone(st.session_state.user_data["phone"], otp)

    if st.session_state.otp:
        entered = st.text_input("Enter OTP")
        if st.button("Verify OTP"):
            if entered == st.session_state.otp:
                st.session_state.otp_verified = True
                st.success("✅ OTP Verified! Account Created.")
                st.session_state.stage = "dashboard"
                st.rerun()
            else:
                st.error("❌ Invalid OTP")

# --- RESTAURANT DASHBOARD ---
def restaurant_page():
    dashboard_header("🏪 Restaurant Owner Dashboard")
    st.subheader("📌 Post Surplus Food")
    with st.form("post_form", clear_on_submit=True):
        restaurant = st.text_input("Restaurant Name",value = st.session_state.user_data["organization"])
        food_item = st.text_input("Food Item")
        quantity = st.text_input("Quantity")
        location = st.text_input("Location")
        expiry_time = st.date_input("Expiry date", date.today())
        submitted = st.form_submit_button("Post Food")

        if submitted:
            new_id = df["id"].max() + 1 if not df.empty else 1
            new_row = {
                "id": new_id,
                "restaurant": restaurant,
                "food_item": food_item,
                "quantity": quantity,
                "location": location,
                "expiry_time": expiry_time,
                "status": "Available",
                "claimed_by": None
            }
            df.loc[len(df)] = new_row
            save_food_db()
            st.success("✅ Food post added successfully!")
            st.rerun()

    st.subheader("📦 Your Posted Items")
    rest_df = df[df["restaurant"] == st.session_state.user_data["organization"]]
    st.dataframe(rest_df)

# --- NGO DASHBOARD ---
def ngo_page():
    dashboard_header("🤝 NGO / Volunteer Dashboard")
    st.subheader("🛒 Browse Available Food")

    col1, col2 = st.columns(2)
    with col1:
        filter_location = st.text_input("Filter by Location")
    with col2:
        filter_time = st.slider("Show items expiring in next (hours)", 1, 24, 6)

    now = datetime.now()
    max_time = now + timedelta(hours=filter_time)

    available_df = df[(df["status"] == "Available") &
                      (pd.to_datetime(df["expiry_time"]) <= max_time)]

    if filter_location:
        available_df = available_df[available_df["location"].str.contains(filter_location, case=False, na=False)]

    if not available_df.empty:
        for _, row in available_df.iterrows():
            expiry_str = pd.to_datetime(row['expiry_time']).strftime("%b %d, %I:%M %p")
            expires_in = pd.to_datetime(row['expiry_time']) - now

            with st.container():
                st.markdown(
                    f"""
                    <div style="
                        background-color: rgba(255,255,255,0.85);
                        padding: 15px;
                        border-radius: 12px;
                        margin-bottom: 12px;
                        box-shadow: 0 2px 6px rgba(0,0,0,0.2);
                    ">
                        <b>{row['food_item']}</b> from <i>{row['restaurant']}</i><br>
                        📦 Qty: {row['quantity']} <br>
                        📍 Location: {row['location']} <br>
                        ⏰ Expires: {expiry_str} ({int(expires_in.total_seconds()//3600)}h left)
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if st.button(f"✅ Claim {row['food_item']} (ID: {row['id']})", key=f"claim_{row['id']}"):
                    df.loc[df["id"] == row["id"], "status"] = "Claimed"
                    df.loc[df["id"] == row["id"], "claimed_by"] = st.session_state.user_data["email"]
                    save_food_db()
                    st.success(f"🎉 You claimed {row['food_item']}!")
                    st.rerun()
    else:
        st.info("No available food right now.")

# --- ADMIN DASHBOARD ---
def admin_page():
    dashboard_header("🛡 Admin Dashboard")
    if df.empty:
        st.info("No food posts yet.")
    else:
        total_posts = len(df)
        available = len(df[df["status"] == "Available"])
        claimed = len(df[df["status"] == "Claimed"])

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Posts", total_posts)
        col2.metric("Available", available)
        col3.metric("Claimed", claimed)

        fig1, ax1 = plt.subplots()
        ax1.pie([available, claimed], labels=["Available", "Claimed"], autopct='%1.1f%%', startangle=90)
        ax1.axis('equal')
        st.pyplot(fig1)

        st.subheader("🍴 Top Restaurants by Posts")
        st.bar_chart(df["restaurant"].value_counts().head(5))

        st.subheader("🙌 Top Volunteers by Claims")
        st.bar_chart(df["claimed_by"].value_counts().head(5))

        st.subheader("📦 Manage Food Posts")
        st.dataframe(df)
        delete_id = st.text_input("Enter Food ID to delete")
        if st.button("Delete Food"):
            if delete_id.isdigit():
                df.drop(df[df["id"] == int(delete_id)].index, inplace=True)
                save_food_db()
                st.success("🗑 Food post deleted!")
                st.rerun()

# --- STAGES ---
if st.session_state.stage == "role":
    st.title("Food Rescue Network - Welcome")
    role = st.radio("Continue as:", ["Provider (Restaurant)", "Receiver (NGO / Volunteer)", "Admin"])

    if st.button("Next ➡"):
        st.session_state.user_data["role"] = role
        if role == "Admin":
            st.session_state.stage = "login"
        else:
            st.session_state.stage = "form"
        st.rerun()

elif st.session_state.stage == "form":
    st.title("📝 Account Registration")

    name = st.text_input("👤 Name")
    email = st.text_input("📧 Email")
    password = st.text_input("🔑 Password", type="password")
    phone = st.text_input("📱 Phone Number")

    org_label = "Restaurant Name" if "Provider" in st.session_state.user_data["role"] else "NGO / Volunteer Name"
    organization = st.text_input(f"🏢 {org_label}")

    if st.button("Confirm & Create Account"):
        if name and email and password and phone and organization:
            if email in st.session_state.accounts:
                st.error("⚠ Email already registered. Please login.")
            else:
                new_account = {
                    "name": name,
                    "email": email,
                    "password": password,
                    "phone": phone,
                    "organization": organization,
                    "role": st.session_state.user_data["role"]
                }
                st.session_state.user_data = new_account
                accounts_df.loc[len(accounts_df)] = new_account
                save_accounts_db()
                st.session_state.stage = "otp"
                st.rerun()
        else:
            st.error("⚠ Please fill in all fields.")

    if st.button("Go to Login"):
        st.session_state.stage = "login"
        st.rerun()

elif st.session_state.stage == "otp":
    otp_verification_flow()

elif st.session_state.stage == "login":
    st.title("🔑 Login to Food Rescue")
    login_tab,forgot_tab = st.tabs(["login","Forgot Password"])

    with login_tab:
        email = st.text_input("📧 Email",key = "login_email")
        password = st.text_input("🔑 Password", type="password",key="login_pass")

        if st.button("Login"):
            if email in st.session_state.accounts and st.session_state.accounts[email]["password"] == password:
                st.session_state.user_data = st.session_state.accounts[email]
                st.session_state.stage = "dashboard"
                st.success("✅ Login successful!")
                st.rerun()
            else:
                st.error("❌ Invalid email or password.")

    with forgot_tab:
        phone = st.text_input("📱 Registered Phone Number", key="forgot_phone")
        new_password = st.text_input("🔑 New Password", type="password", key="forgot_pass")
        if st.button("Reset Password"):
            matched_accounts = [acc for acc in st.session_state.accounts.values() if acc["phone"] == phone]
            if matched_accounts:
                account = matched_accounts[0]
                email_to_update = account["email"]
                st.session_state.accounts[email_to_update]["password"] = new_password
                st.session_state.user_data = st.session_state.accounts[email_to_update]
                accounts_df.loc[accounts_df["email"] == email_to_update, "password"] = new_password
                save_accounts_db()
                st.success("✅ Password reset successful! You can now login.")
                st.rerun()
            else:
                st.error("❌ Phone number not found.")

    if st.button("Go to Register"):
        st.session_state.stage = "role"
        st.rerun()

elif st.session_state.stage == "dashboard":
    role = st.session_state.user_data["role"]
    if role == "Admin":
        admin_page()
    elif "Provider" in role:
        restaurant_page()
    elif "Receiver" in role:
        ngo_page()
