import streamlit as st
import re
import json
from datetime import datetime
from pathlib import Path
import subprocess
import sys

st.set_page_config(page_title="JD → Email Sender", layout="wide")

# ---------- LOAD CSS ----------
def load_css():
    css_path = Path(".streamlit/styles.css")
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

load_css()

# ---------- HELPERS ----------
def extract_emails(text):
    pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    return list(set(re.findall(pattern, text)))

def create_json(emails, jd):
    data = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for e in emails:
        data.append({
            "emails": [e],
            "job_description": jd,
            "extraction_date": now
        })
    Path("linkedin_emails_jds.json").write_text(json.dumps(data, indent=2))

# ---------- UI ----------
st.markdown('<div class="main-title">📧 JD → Smart Email Sender</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Paste JD and auto send resume emails.</div>', unsafe_allow_html=True)

jd = st.text_area("Paste Job Description", height=250)

if jd:
    emails = extract_emails(jd)

    col1, col2 = st.columns(2)
    col1.markdown(f'<div class="metric-card">Emails Found<br><b>{len(emails)}</b></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="metric-card">Words<br><b>{len(jd.split())}</b></div>', unsafe_allow_html=True)

    chips = "".join([f'<span class="email-chip">{e}</span>' for e in emails])
    st.markdown(chips, unsafe_allow_html=True)

if st.button("🚀 Extract Emails & Send", use_container_width=True):
    emails = extract_emails(jd)
    if not emails:
        st.error("No emails found")
        st.stop()

    create_json(emails, jd)

    st.success("Sending started...")

    process = subprocess.Popen(
        [sys.executable, "email_sender.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    logs = ""
    with st.expander("Live Logs"):
        for line in process.stdout:
            logs += line
            st.code(logs)
