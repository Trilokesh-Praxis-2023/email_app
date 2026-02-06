#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Email sender script (updated)
- Adds config option `send_today_only = yes|no`
- When enabled, only sends emails extracted today (extraction_date or added_timestamp)
  and ensures uniqueness across today's extracted email addresses.
- Preserves original safeguards: skip personal emails, avoid recently-sent addresses,
  avoid duplicate subject/email combos, attach resume, and atomic history writes.
"""

import re
import difflib
import time
import json
import ssl
import smtplib
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

YOUR_NAME = os.getenv("YOUR_NAME")
YOUR_EMAIL = os.getenv("SENDER_EMAIL")
YOUR_PHONE = os.getenv("YOUR_PHONE")


# ---------------- USER DETAILS ---------------- #
YOUR_NAME = "Trilokesh Ranjan Sarkar"
YOUR_EMAIL = "trilokesh086@gmail.com"
YOUR_PHONE = "8910384107"

# ---------------- PATHS ---------------- #
PATHS = {
    "config": r"email_config.txt",
    "resume": r"Trilokesh_Resume.pdf",
    "emails": r"linkedin_emails_jds.json",
    "history": r"email_sending_history.json"
}

# ---------------- CORE HELPERS ---------------- #

def load_config():
    return {
        "smtp_server": os.getenv("SMTP_SERVER"),
        "smtp_port": os.getenv("SMTP_PORT", 587),
        "sender_email": os.getenv("SENDER_EMAIL"),
        "sender_password": os.getenv("SENDER_PASSWORD"),
        "delay": os.getenv("DELAY", 15),
        "send_today_only": os.getenv("SEND_TODAY_ONLY", "yes"),
    }


def load_history():
    p = Path(PATHS["history"])
    if not p.exists():
        return {"sent_emails": [], "total_sent": 0}
    try:
        hist = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(hist, dict):
            raise ValueError("Invalid format")
        hist.setdefault("sent_emails", [])
        hist.setdefault("total_sent", 0)
        return hist
    except Exception as e:
        print(f"[WARNING] Could not parse history JSON ({e}), resetting history.")
        return {"sent_emails": [], "total_sent": 0}

def save_history(hist):
    """Safely write email history to JSON (atomic replace)."""
    hist_path = Path(PATHS["history"])
    tmp_path = hist_path.with_suffix(".tmp")
    if "sent_emails" not in hist or not isinstance(hist["sent_emails"], list):
        hist["sent_emails"] = []
    if "total_sent" not in hist:
        hist["total_sent"] = len(hist["sent_emails"])
    tmp_path.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(hist_path)

def attach_resume(msg):
    resume_path = Path(PATHS["resume"])
    if not resume_path.exists():
        print(f"[WARNING] Resume not found: {resume_path}")
        return
    with resume_path.open("rb") as f:
        part = MIMEApplication(f.read(), _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=resume_path.name)
        msg.attach(part)
    print("[INFO] Resume attached.")

# ---------------- DATE / FILTER HELPERS ---------------- #

def try_parse_date(dt_str):
    """Try to parse a variety of date formats; return datetime.date or None."""
    if not dt_str or not isinstance(dt_str, str):
        return None
    s = dt_str.strip()
    fmts = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S.%f"
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

def is_extracted_today(entry):
    """Return True if the entry's extraction_date or added_timestamp is today."""
    today = datetime.now().date()
    dt = (entry.get("extraction_date") or entry.get("added_timestamp") or "").strip()
    if not dt:
        return False
    parsed = try_parse_date(dt)
    return parsed == today

# ---------------- LOGIC HELPERS ---------------- #

def is_email_sent_recently(hist, email, days=100):
    cutoff_date = datetime.now() - timedelta(days=days)
    for e in hist.get("sent_emails", []):
        try:
            sent_dt = datetime.strptime(e.get("sent_date", ""), "%Y-%m-%d %H:%M:%S")
            if e.get("to_email", "").lower() == email.lower() and sent_dt >= cutoff_date:
                return True
        except Exception:
            continue
    return False



def extract_role(text):
    roles = ["data analyst", "business data engineer", "data scientist",
             "data engineer", "business analyst", "machine learning engineer"]
    text_lower = (text or "").lower()
    pattern = re.compile(r"\b(?:data|business|machine|learning|scientist|engineer|analyst|specialist|consultant)\b(?:\s+\w+){0,4}")
    candidates = pattern.findall(text_lower)
    best_role, highest_ratio = "Data Analyst", 0.0
    for candidate in candidates:
        for role in roles:
            ratio = difflib.SequenceMatcher(None, candidate, role).ratio()
            if ratio > highest_ratio and ratio > 0.6:
                highest_ratio, best_role = ratio, role.title()
    return best_role

def extract_name(email, fallback="Hiring Manager"):
    parts = email.split('@')[0]
    name_parts = re.split(r'[._\-]', parts)
    name = " ".join([p.capitalize() for p in name_parts if p.isalpha()])
    return name if len(name.split()) <= 3 and name else fallback

def is_personal_email(email):
    personal_domains = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "live.com", "icloud.com", "aol.com", "mail.com",
        "gmx.com", "protonmail.com", "webspiders.com", "affinitysolutions.com",
        "affinity.solutions.com", "coduzion.com"
    }
    try:
        domain = email.lower().split("@", 1)[-1]
    except Exception:
        return True
    return domain in personal_domains

def extract_company(email, fallback="your company"):
    personal_domains = [
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "live.com", "icloud.com", "aol.com", "mail.com", "gmx.com",
        "protonmail.com", "webspiders.com", "affinitysolutions.com", 
        "affinity.solutions.com", "coduzion.com"]
    domain = email.lower().split('@')[-1]
    domain_main = domain.split('.')[0] if domain else ""
    if domain in personal_domains:
        return fallback
    company = re.sub(r'[^a-zA-Z0-9\-]', ' ', domain_main).strip()
    return company.capitalize() if company else fallback

# ---------------- EMAIL GENERATION / SENDING ---------------- #

def compose_email_subject(role, company):
    return f"🚀 Application for {role} at {company}"


def compose_email_body(author, company, role, your_name, your_email, your_phone):
    return f"""
<p>Dear <b>{author}</b>,</p>

<p>
I hope you are doing well. I am writing to express my interest in the <b>{role}</b> role at <b>{company}</b>. 
I currently work as a <b>Data Analyst at Web Spiders</b> and hold a <b>PG Diploma in Data Science</b> from Praxis Business School.
</p>

<p>
💡 I specialize in <b>data analysis, dashboarding, automation pipelines</b>, and <b>end-to-end AI workflows</b>.  
I work daily with <b>Python, SQL, Pandas</b>, and BI tools to deliver insights and support decision-making.
</p>

<p>
📊 My recent work includes <b>ETL pipelines, data quality checks, Power BI dashboards, Selenium automation</b>, 
and <b>Video AI analytics</b> for retail behavior insights. I enjoy building solutions that improve accuracy and efficiency.
</p>

<p>
📚 I have also published research on <b>adversarial robustness</b>, evaluating <b>FGSM</b> and <b>CW attacks</b> with defensive distillation 
(<i>arXiv:2404.04245</i>).
</p>

<p>
I would love the opportunity to contribute my <b>data analytics</b> and <b>automation</b> skills to <b>{company}</b>.  
Please find my resume attached.
</p>

<p>
Best regards,<br>
<b>{your_name}</b><br>
📧 <b>{your_email}</b><br>
📱 <b>{your_phone}</b>
</p>
"""


def send_email(cfg, to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{YOUR_NAME} <{cfg['sender_email']}>"
        msg["To"] = to_email
        msg["Subject"] = subject.strip()
        msg.attach(MIMEText(body, "html", "utf-8"))
        attach_resume(msg)

        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(cfg["smtp_server"], int(cfg["smtp_port"]), context=context) as server:
            server.login(cfg["sender_email"], cfg["sender_password"])
            server.send_message(msg)

        print(f"[INFO] Sent successfully → {to_email}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to send email to {to_email}: {e}")
        return False

# ---------------- MAIN FUNCTION ---------------- #

def main():
    cfg = load_config()
    if not cfg:
        print("[WARN] No config found. Please ensure email_config.txt exists with smtp settings.")
    # parse send_today_only flag (default: no)
    send_today_only = str(cfg.get("send_today_only", "yes")).strip().lower() in ("yes", "true", "1", "y")

    emails_path = Path(PATHS["emails"])
    if not emails_path.exists():
        print(f"[ERROR] Email data file not found: {emails_path}")
        return

    try:
        raw = json.loads(emails_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[ERROR] Invalid JSON in: {emails_path} ({e})")
        return

    # Normalize entries to list (preserve list if it's a list)
    entries = raw if isinstance(raw, list) else (raw.get("data") if isinstance(raw, dict) and isinstance(raw.get("data"), list) else ([raw] if isinstance(raw, dict) else []))
    print(f"[INFO] Loaded {len(entries)} entries from {emails_path}")

    # If send_today_only, filter entries to those extracted today
    if send_today_only:
        entries = [e for e in entries if is_extracted_today(e)]
        print(f"[INFO] send_today_only enabled → {len(entries)} entries extracted today")

    hist = load_history()
    hist.setdefault("sent_emails", [])
    hist.setdefault("total_sent", 0)

    total_sent = 0
    seen_today_emails = set()  # track unique emails when send_today_only enabled

    for entry in entries:
        job_desc = entry.get("job_description", "") or ""
        raw_emails = entry.get("emails", [])  # could be list or string
        if isinstance(raw_emails, str):
            # try comma separated
            email_list = [e.strip() for e in re.split(r'[,\n;]+', raw_emails) if e.strip()]
        elif isinstance(raw_emails, list):
            email_list = [e.strip() for e in raw_emails if isinstance(e, str) and e.strip()]
        else:
            email_list = []

        if not email_list:
            continue

        role = extract_role(job_desc)

        for to in email_list:
            if not to or "@" not in to:
                continue
            # If send_today_only, enforce uniqueness across today's extracted emails
            if send_today_only:
                if to.lower() in seen_today_emails:
                    print(f"[INFO] Skipping duplicate today email: {to}")
                    continue

            author = extract_name(to)
            company = extract_company(to)
            subject = compose_email_subject(role, company)
            body = compose_email_body(author, company, role, YOUR_NAME, YOUR_EMAIL, YOUR_PHONE)

            if is_email_sent_recently(hist, to):
                print(f"[INFO] Already sent recently: {to}")
                continue

            if is_personal_email(to):
                print(f"[INFO] Skipping personal email address: {to}")
                continue

            # check duplicate subject/email in history
            existing = [
                e for e in hist["sent_emails"]
                if e.get("to_email", "").lower() == to.lower()
                and e.get("subject", "").strip().lower() == subject.strip().lower()
            ]
            if existing:
                print(f"[INFO] Duplicate subject/email combo detected — skipping: {to}")
                continue

            # Send
            if send_email(cfg, to, subject, body):
                entry_data = {
                    "to_email": to,
                    "subject": subject,
                    "sent_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "author": author,
                    "company": company
                }
                hist["sent_emails"].append(entry_data)
                hist["total_sent"] = len(hist["sent_emails"])
                save_history(hist)
                total_sent += 1
                print(f"[SAVE] History updated. Total Sent: {total_sent}")

                # Mark as seen for today's uniqueness enforcement
                if send_today_only:
                    seen_today_emails.add(to.lower())

            # Respect delay from config (default 15s)
            try:
                delay = int(cfg.get("delay", 15))
            except Exception:
                delay = 15
            time.sleep(delay)

    print(f"\n[INFO] Completed — Total Sent This Run: {total_sent}")

if __name__ == "__main__":
    main()
