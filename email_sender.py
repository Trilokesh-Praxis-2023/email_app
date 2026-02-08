import re
import time
from datetime import datetime, timedelta

import requests
import streamlit as st

# ---------------- CONFIG FROM SECRETS ---------------- #

YOUR_NAME = st.secrets["YOUR_NAME"]
YOUR_EMAIL = st.secrets["SENDER_EMAIL"]
YOUR_PHONE = st.secrets["YOUR_PHONE"]


def load_config():
    return {
        "sender_email": st.secrets["SENDER_EMAIL"],
        "delay": 15,
    }


# ---------------- HISTORY (SESSION STATE) ---------------- #

def load_history():
    if "email_history" not in st.session_state:
        st.session_state.email_history = {
            "sent_emails": [],
            "total_sent": 0
        }
    return st.session_state.email_history


def save_history(hist):
    st.session_state.email_history = hist


# ---------------- RESUME LINK ---------------- #

def get_resume_link():
    return "https://drive.google.com/file/d/18MPz2-JIlLD58UUKtqM8Q_W-9mi7LLp6/view"


# ---------------- HELPERS ---------------- #

def extract_role(text):
    roles = ["data analyst", "data scientist", "data engineer",
             "business analyst", "machine learning engineer"]
    text_lower = (text or "").lower()
    for r in roles:
        if r in text_lower:
            return r.title()
    return "Data Analyst"


def extract_name(email, fallback="Hiring Manager"):
    parts = email.split('@')[0]
    name_parts = re.split(r'[._\-]', parts)
    name = " ".join([p.capitalize() for p in name_parts if p.isalpha()])
    return name if name else fallback


def is_personal_email(email):
    personal = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "live.com", "icloud.com", "aol.com", "mail.com", "gmx.com",
        "protonmail.com", "webspiders.com", "affinitysolutions.com", 
        "affinity.solutions.com", "coduzion.com"}
    
    domain = email.split("@")[-1].lower()
    return domain in personal


def extract_company(email):
    domain = email.split("@")[-1]
    return domain.split(".")[0].capitalize()


def is_email_sent_recently(hist, email, days=0):
    cutoff = datetime.now() - timedelta(days=days)
    for e in hist["sent_emails"]:
        dt = datetime.strptime(e["sent_date"], "%Y-%m-%d %H:%M:%S")
        if e["to_email"].lower() == email.lower() and dt >= cutoff:
            return True
    return False


# ---------------- EMAIL CONTENT ---------------- #

def compose_email_subject(role, company):
    return f"Application for {role} at {company}"


def compose_email_body(author, company, role):
    return f"""
<p>Dear <b>{author}</b>,</p>

<p>
I hope you are doing well. I am writing to express my interest in the <b>{role}</b> role at <b>{company}</b>. 
I currently work as a <b>Data Analyst</b> with strong experience in automation, dashboards, ETL pipelines, and AI analytics.
</p>

<p>
💡 I specialize in <b>data analysis, dashboarding, automation pipelines</b>, and <b>end-to-end AI workflows</b>.
</p>

<p>
📊 My recent work includes <b>ETL pipelines, data quality checks, Power BI dashboards, Selenium automation</b>, 
and <b>Video AI analytics</b>.
</p>

<p>
You can view my resume here: 
<a href="{get_resume_link()}">View Resume</a>
</p>

<p>
Best regards,<br>
<b>{YOUR_NAME}</b><br>
📧 {YOUR_EMAIL}<br>
📱 {YOUR_PHONE}
</p>
"""


# ---------------- EMAILJS SEND ---------------- #

def send_email(to_email, subject, body):
    url = "https://api.emailjs.com/api/v1.0/email/send"

    payload = {
        "service_id": st.secrets["EMAILJS_SERVICE_ID"],
        "template_id": st.secrets["EMAILJS_TEMPLATE_ID"],
        "user_id": st.secrets["EMAILJS_PUBLIC_KEY"],
        "template_params": {
            "to_name": extract_name(to_email),
            "from_name": YOUR_NAME,
            "subject": subject,
            "message": body,
            "reply_to": YOUR_EMAIL,
            "to_email": to_email
        }
    }

    r = requests.post(url, json=payload, headers={"Content-Type": "application/json"})

    st.write("📨 EmailJS Status:", r.status_code)
    st.write("📨 EmailJS Response:", r.text)

    return r.status_code == 200


# ---------------- MAIN PROCESS ---------------- #

def process_and_send(entries):
    cfg = load_config()
    hist = load_history()
    total = 0

    for entry in entries:
        jd = entry.get("job_description", "")
        emails = entry.get("emails", [])

        role = extract_role(jd)

        for to in emails:
            if not to or is_personal_email(to):
                continue

            if is_email_sent_recently(hist, to):
                continue

            company = extract_company(to)
            subject = compose_email_subject(role, company)
            body = compose_email_body(extract_name(to), company, role)

            if send_email(to, subject, body):
                hist["sent_emails"].append({
                    "to_email": to,
                    "subject": subject,
                    "sent_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                hist["total_sent"] += 1
                save_history(hist)
                total += 1

            time.sleep(cfg["delay"])

    return total
