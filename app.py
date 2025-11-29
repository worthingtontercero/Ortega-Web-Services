from flask import Flask, render_template, request, redirect, url_for, flash
import csv
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # loads .env if present

APP_NAME = "Ortega Web Services"

DEFAULT_EMAIL = "elpasosites@gmail.com"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret")  # change in production

# Optional SMTP settings (set in environment or .env file)
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587")) if os.getenv("SMTP_PORT") else None
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

FROM_EMAIL = os.getenv("FROM_EMAIL", DEFAULT_EMAIL)
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", DEFAULT_EMAIL)

MESSAGES_CSV = "messages.csv"


def save_message(row: dict):
    """Append contact message to CSV (creates file + header if missing)."""
    header = ["timestamp", "name", "business", "contact", "message"]
    write_header = not os.path.exists(MESSAGES_CSV)
    with open(MESSAGES_CSV, "a", newline="", encoding="utf-8") as f:
        import csv as _csv
        writer = _csv.DictWriter(f, fieldnames=header)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def send_email_notification(to_email: str, subject: str, body: str) -> bool:
    """Try to send an email via SMTP if configured. Return True if sent."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to_email
        msg.set_content(body)

        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=60)
            server.login(SMTP_USER, SMTP_PASS)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT or 587, timeout=60)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)

        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        app.logger.error("SMTP send failed: %s", e)
        return False


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", app_name=APP_NAME)


@app.route("/contact", methods=["POST"])
def contact():
    name = request.form.get("name", "").strip()
    business = request.form.get("business", "").strip()
    contact_info = request.form.get("contact", "").strip()
    message_text = request.form.get("message", "").strip()

    if not (name and (contact_info or message_text)):
        flash("Please provide at least your name and a contact method or message.", "error")
        return redirect(url_for("index") + "#contact")

    timestamp = datetime.utcnow().isoformat()
    row = {
        "timestamp": timestamp,
        "name": name,
        "business": business,
        "contact": contact_info,
        "message": message_text,
    }

    # Save locally
    try:
        save_message(row)
    except Exception as e:
        app.logger.error("Failed to save message: %s", e)
        flash("Sorry — could not save your message. Try again later.", "error")
        return redirect(url_for("index") + "#contact")

    # Email the message to your contact address (if SMTP configured)
    email_subject = f"[Website Lead] {business or name}"
    email_body = (
        f"New lead received:\n\n"
        f"Name: {name}\n"
        f"Business: {business}\n"
        f"Contact: {contact_info}\n\n"
        f"Message:\n{message_text}\n\n"
        f"Received: {timestamp} UTC"
    )

    emailed = send_email_notification(NOTIFY_EMAIL, email_subject, email_body)
    if emailed:
        flash("Thanks — your message was sent. We'll be in touch.", "success")
    else:
        flash("Thanks — your message was recorded. (Email not configured.)", "success")

    return redirect(url_for("index") + "#contact")


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", 5000)), debug=debug)
