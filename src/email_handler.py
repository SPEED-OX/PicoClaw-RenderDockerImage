import aiosmtplib
import aioimaplib
from email.mime.text import MIMEText
from typing import List, Optional
from src import config

async def send_email(to: str, subject: str, body: str) -> str:
    if not config.EMAIL_ADDRESS or not config.EMAIL_PASSWORD:
        return "Error: Email credentials not configured."
    
    try:
        message = MIMEText(body, "plain")
        message["From"] = config.EMAIL_ADDRESS
        message["To"] = to
        message["Subject"] = subject
        
        await aiosmtplib.send(
            message,
            hostname=config.SMTP_SERVER,
            port=config.SMTP_PORT,
            username=config.EMAIL_ADDRESS,
            password=config.EMAIL_PASSWORD,
            use_tls=True,
        )
        return f"Email sent to {to}"
    except Exception as e:
        return f"Error sending email: {str(e)}"

async def get_inbox() -> str:
    if not config.EMAIL_ADDRESS or not config.EMAIL_PASSWORD:
        return "Error: Email credentials not configured."
    
    try:
        imap = aioimaplib.IMAP4_SSL(config.IMAP_SERVER)
        await imap.login(config.EMAIL_ADDRESS, config.EMAIL_PASSWORD)
        await imap.select("INBOX")
        
        status, messages = await imap.search(None, "UNSEEN")
        if status != "OK":
            await imap.logout()
            return "Error: Could not search inbox."
        
        message_ids = messages[0].split()
        if not message_ids:
            await imap.logout()
            return "No unread emails."
        
        recent_ids = message_ids[-5:] if len(message_ids) > 5 else message_ids
        results = []
        
        for msg_id in reversed(recent_ids):
            status, msg_data = await imap.fetch(msg_id, "(ENVELOPE)")
            if status == "OK" and msg_data:
                envelope = msg_data[0]
                if hasattr(envelope, 'subject'):
                    subject = envelope.subject or "(No subject)"
                    from_addr = envelope.from_[0] if envelope.from_ else "Unknown"
                    results.append(f"From: {from_addr}\nSubject: {subject}")
        
        await imap.logout()
        
        if results:
            return "Recent unread emails:\n\n" + "\n\n---\n\n".join(results)
        return "No unread emails."
    except Exception as e:
        return f"Error checking inbox: {str(e)}"
