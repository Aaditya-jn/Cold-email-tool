#!/usr/bin/env python3
"""
Cold Email Automation Tool
---------------------------
Stores your default cold-email template once. For each send, you give
it a recipient email + an optional job description (JD). If the JD's
role focus differs from your template's default role, Gemini rewrites
the email to match the JD while keeping your voice/structure. You
always see a preview and must confirm before it sends via Gmail API.

Setup (one-time):
    1. pip install google-auth google-auth-oauthlib google-api-python-client google-genai
    2. Enable Gmail API in Google Cloud Console, download OAuth client
       credentials as `credentials.json` in this folder.
    3. Get a Gemini API key: https://aistudio.google.com/app/apikey
       export GEMINI_API_KEY="your-key-here"
    4. Run: python cold_email.py setup-template
       (paste your default cold email template once)
    5. Run: python cold_email.py send
       (enter recipient email + optional JD each time)

Files created in this folder:
    template.json   - your stored default template
    sent_log.json   - log of every email sent (prevents duplicate sends)
    credentials.json - your Gmail OAuth client (you provide this)
    token.json      - auto-created after first Gmail login
    resume.pdf      - put your resume here; it's auto-attached to every
                      email if present (skipped silently if missing)
"""

import os
import sys
import json
import base64
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime

TEMPLATE_FILE = "template.json"
LOG_FILE = "sent_log.json"
RESUME_FILE = "resume.pdf"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


# ---------- Storage helpers ----------

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ---------- Template setup ----------

def setup_template():
    print("Paste your default cold email template below.")
    print("Include a line starting with 'SUBJECT:' for the subject line.")
    print("End input with a single line containing only: END")
    print("-" * 50)
    lines = []
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    full_text = "\n".join(lines)

    subject = ""
    body_lines = []
    for line in lines:
        if line.strip().upper().startswith("SUBJECT:"):
            subject = line.split(":", 1)[1].strip()
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()

    default_role = input(
        "\nWhat role is this template originally written for? "
        "(e.g. 'Full Stack Engineer'): "
    ).strip()

    save_json(TEMPLATE_FILE, {
        "subject": subject,
        "body": body,
        "default_role": default_role,
    })
    print(f"\nSaved template.json (default role: {default_role})")


# ---------- Gemini rewrite ----------

def adapt_email_with_gemini(template, jd_text):
    from google import genai

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: set GEMINI_API_KEY environment variable first.")
        sys.exit(1)
    client = genai.Client(api_key=api_key)

    prompt = f"""You are helping adapt a cold outreach email to match a specific job description.

MY DEFAULT COLD EMAIL TEMPLATE (originally written for a "{template['default_role']}" role):
Subject: {template['subject']}

Body:
{template['body']}

---

JOB DESCRIPTION OF THE ROLE I'M NOW APPLYING TO:
{jd_text}

---

TASK:
1. Compare the JD's actual role focus to my template's default role ("{template['default_role']}").
2. If they differ meaningfully (e.g. template is for Full Stack but JD is for AI Engineering),
   rewrite the email so the skills, project mentions, and framing match what the JD is
   actually asking for. Keep my original voice, tone, structure, and length as close as
   possible — only adjust the role-specific content.
3. If the JD role already matches my template's default role closely, return the template
   UNCHANGED.
4. Never invent skills, experience, or claims I didn't already mention in the template.
   Only re-emphasize or re-frame what's already there to fit the JD better.

Return ONLY valid JSON, no markdown fences, no preamble, in this exact format:
{{"subject": "...", "body": "...", "was_changed": true or false}}
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    text = response.text.strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        print("WARNING: Could not parse Gemini's response as JSON. Raw output:")
        print(text)
        sys.exit(1)
    return result


# ---------- Gmail send ----------

def get_gmail_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                print("ERROR: credentials.json not found. See setup instructions at top of this file.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        save_json("token.json", json.loads(creds.to_json()))
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=creds)


def send_email(to_email, subject, body, attachment_path=None):
    service = get_gmail_service()

    if attachment_path and os.path.exists(attachment_path):
        message = MIMEMultipart()
        message["to"] = to_email
        message["subject"] = subject
        message.attach(MIMEText(body))

        ctype, encoding = mimetypes.guess_type(attachment_path)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)

        with open(attachment_path, "rb") as f:
            part = MIMEBase(maintype, subtype)
            part.set_payload(f.read())
        encoders.encode_base64(part)
        filename = os.path.basename(attachment_path)
        part.add_header("Content-Disposition", f"attachment; filename={filename}")
        message.attach(part)
    else:
        message = MIMEText(body)
        message["to"] = to_email
        message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


# ---------- Main send flow ----------

def send_flow():
    template = load_json(TEMPLATE_FILE, None)
    if not template:
        print("No template found. Run: python cold_email.py setup-template")
        sys.exit(1)

    to_email = input("Recipient email: ").strip()
    print("Paste the job description (optional). Leave blank + Enter to skip.")
    print("If pasting multi-line, end with a single line: END")
    first_line = input()
    if first_line.strip() == "":
        jd_text = ""
    else:
        jd_lines = [first_line]
        if first_line.strip() != "END":
            while True:
                line = input()
                if line.strip() == "END":
                    break
                jd_lines.append(line)
        jd_text = "\n".join(jd_lines).strip()

    if jd_text:
        print("\nAdapting email to JD with Gemini...")
        result = adapt_email_with_gemini(template, jd_text)
        subject, body = result["subject"], result["body"]
        if result.get("was_changed"):
            print("-> Email was adapted to match this JD.")
        else:
            print("-> JD matches your default role; template used as-is.")
    else:
        subject, body = template["subject"], template["body"]

    has_resume = os.path.exists(RESUME_FILE)

    print("\n" + "=" * 60)
    print(f"TO: {to_email}")
    print(f"SUBJECT: {subject}")
    print("-" * 60)
    print(body)
    print("=" * 60)
    print(f"ATTACHMENT: {RESUME_FILE} ({'found' if has_resume else 'NOT FOUND — will send without it'})")

    log = load_json(LOG_FILE, [])
    already_sent = any(e["to"] == to_email for e in log)
    if already_sent:
        print(f"\nNOTE: You've already emailed {to_email} before (see sent_log.json).")

    confirm = input("\nSend this email? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled. Nothing sent.")
        return

    send_email(to_email, subject, body, attachment_path=RESUME_FILE if has_resume else None)
    log.append({
        "to": to_email,
        "subject": subject,
        "jd_provided": bool(jd_text),
        "resume_attached": has_resume,
        "timestamp": datetime.now().isoformat(),
    })
    save_json(LOG_FILE, log)
    print(f"\nSent to {to_email} and logged.")


# ---------- Entry point ----------

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python cold_email.py setup-template   # one-time: save your template")
        print("  python cold_email.py send             # send an email")
        print("  python cold_email.py log              # view sent history")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "setup-template":
        setup_template()
    elif cmd == "send":
        send_flow()
    elif cmd == "log":
        log = load_json(LOG_FILE, [])
        if not log:
            print("No emails sent yet.")
        for entry in log:
            print(f"{entry['timestamp']}  ->  {entry['to']}  ({entry['subject']})")
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
