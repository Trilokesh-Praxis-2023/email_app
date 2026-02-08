import streamlit as st
import re
from pathlib import Path
from datetime import datetime

from email_sender import process_and_send

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

# ---------- UI ----------
st.markdown('<div class="main-title">📧 JD → Smart Email Sender</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-text">Paste JD and automatically send resume emails.</div>', unsafe_allow_html=True)

jd = st.text_area("Paste Job Description", height=250)

if jd:
    emails = extract_emails(jd)

    col1, col2 = st.columns(2)
    col1.markdown(f'<div class="metric-card">Emails Found<br><b>{len(emails)}</b></div>', unsafe_allow_html=True)
    col2.markdown(f'<div class="metric-card">Words<br><b>{len(jd.split())}</b></div>', unsafe_allow_html=True)

    chips = "".join([f'<span class="email-chip">{e}</span>' for e in emails])
    st.markdown(chips, unsafe_allow_html=True)

# ---------- SEND BUTTON ----------
if st.button("🚀 Extract Emails & Send", use_container_width=True):
    emails = extract_emails(jd)

    if not emails:
        st.error("No emails found in JD")
        st.stop()

    entries = [{
        "emails": emails,
        "job_description": jd,
        "extraction_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }]

    with st.spinner("Sending emails..."):
        sent = process_and_send(entries)

    st.success(f"✅ {sent} emails sent successfully!")
