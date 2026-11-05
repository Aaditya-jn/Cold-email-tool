# Cold Email Automation Tool

A CLI tool that stores your default cold-email template, adapts it to a
job description (JD) when needed using Gemini, shows you a preview, and
sends it via your Gmail account — only after you confirm.

## How it works

1. **One-time:** you save your default cold email template (the one
   written for Full Stack roles).
2. **Each send:** you give the tool a recipient email + paste the JD
   (optional).
3. If the JD's role differs from your template's default role, Gemini
   rewrites the email to fit (e.g. Full Stack → AI Engineering) while
   keeping your voice and structure. If it already matches, nothing changes.
4. You see the exact subject + body before anything goes out.
5. On confirm, it sends via Gmail API and logs it (so you can see who
   you've already emailed).

## Setup

### 1. Install dependencies
```bash
pip install google-auth google-auth-oauthlib google-api-python-client google-genai
```

If you see an `externally-managed-environment` error, create a virtual
environment first:
```bash
python3 -m venv venv
source venv/bin/activate      # run this every time you open a new terminal
pip install google-auth google-auth-oauthlib google-api-python-client google-genai
```

### 2. Gmail API credentials
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a project.
2. Enable the **Gmail API**.
3. Go to "Credentials" → "Create Credentials" → "OAuth client ID" → choose **Desktop app**.
4. Download the JSON file, rename it to `credentials.json`, put it in this folder.
5. First time you run `send`, a browser window will open asking you to log in and
   authorize — this creates `token.json` automatically after that, so you won't
   need to log in again.

### 3. Gemini API key
1. Get a free key at [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Set it as an environment variable:
   ```bash
   export GEMINI_API_KEY="your-key-here"
   ```
   (Add this line to your `~/.bashrc` or `~/.zshrc` so you don't have to redo it every session.)

## Usage

```bash
# One-time: save your cold email template
python cold_email.py setup-template

# For every outreach:
python cold_email.py send

# See everyone you've emailed so far:
python cold_email.py log
```

### When saving your template
Paste it with a `SUBJECT:` line first, e.g.:
```
SUBJECT: Full Stack Engineer with AI product experience — Aaditya
Hi {name},

I'm Aaditya, a full-stack developer who ships AI-integrated products...
...
END
```
Then it'll ask what role this template was originally written for
(e.g. `Full Stack Engineer`) — this is what Gemini compares every JD against.

## Resume attachment

Put your resume PDF in this folder, named exactly `resume.pdf`. It is
attached automatically to every email you send — no setup needed. If
`resume.pdf` isn't found, the tool still sends the email (just without
an attachment) and tells you so in the preview before you confirm.

Your resume PDF is already included in this download, pre-renamed to
`resume.pdf` — just keep it in the same folder as `cold_email.py`.

> Note: your resume is also hosted at https://aadityajain.vercel.app/resume.pdf —
> that link is just for reference/sharing elsewhere. The script attaches
> the local `resume.pdf` file directly; it doesn't fetch from a URL.

## Notes / things to adjust
- The Gemini prompt is written to **never invent new skills/claims** —
  it only reframes what's already in your template. Edit the prompt in
  `adapt_email_with_gemini()` if you want it to be more/less aggressive.
- `sent_log.json` just warns you about duplicate sends — it doesn't block them.
- This sends from your own Gmail, so it's subject to Gmail's sending limits
  (500/day for regular accounts). Fine for cold outreach volumes.
- If you want HR name personalization ({name} in the template), you can
  extend `send_flow()` to also prompt for the recipient's name and `.replace()`
  it into subject/body before the Gemini step.
