from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import imaplib
import email
from email.header import decode_header
import os
import json
import spacy
from dotenv import load_dotenv
import requests

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à limiter en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    nlp = spacy.load("fr_core_news_md")
except:
    nlp = spacy.load("fr_core_news_sm")

class MailItem(BaseModel):
    id: str
    subject: str
    sender: str
    date: str
    body: str
    importance: str
    score: float
    mailbox: str  # Ajout de l'indicateur de boîte mail

NER_WEIGHTS = {
    "ORG": 0.3,
    "PERSON": 0.2,
    "MONEY": 0.4,
    "DATE": 0.1,
    "GPE": 0.2,
    "LOC": 0.2
}

KEYWORDS = {
    "urgent": 0.5,
    "répondre": 0.3,
    "mise en demeure": 0.7,
    "facture": 0.2,
    "relance": 0.4
}

def score_message(body: str, subject: str) -> float:
    score = 0.0
    text = f"{subject.lower()} {body.lower()}"
    for kw, weight in KEYWORDS.items():
        if kw in text:
            score += weight
    doc = nlp(subject + "\n" + body)
    for ent in doc.ents:
        score += NER_WEIGHTS.get(ent.label_, 0.0)
    return min(score, 1.0)

def log_mail(data: dict):
    os.makedirs("logs", exist_ok=True)
    with open("logs/mail_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def refresh_token():
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    refresh_token = os.getenv("REFRESH_TOKEN")

    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }
    r = requests.post(token_url, data=payload)
    if r.status_code == 200:
        return r.json().get("access_token")
    else:
        raise Exception("Échec du rafraîchissement OAuth2")

def connect_imap(account):
    host = account["IMAP_HOST"]
    user = account["IMAP_USER"]
    password = account.get("IMAP_PASS")
    access_token = account.get("ACCESS_TOKEN")
    refresh = account.get("REFRESH_TOKEN")

    mail = imaplib.IMAP4_SSL(host)

    if not access_token and refresh:
        # Optionnel: rafraîchir le token si besoin (à adapter selon le provider)
        access_token = refresh_token()

    if access_token:
        auth_string = f"user={user}\1auth=Bearer {access_token}\1\1"
        mail.authenticate("XOAUTH2", lambda x: auth_string.encode())
    elif password:
        mail.login(user, password)
    else:
        raise HTTPException(status_code=401, detail=f"Aucune méthode d'authentification disponible pour {user}.")

    return mail

def fetch_emails_imap(accounts, mailbox="INBOX", max_mails=10):
    all_messages = []
    for account in accounts:
        try:
            mail = connect_imap(account)
            mail.select(mailbox)
            typ, data = mail.search(None, 'ALL')
            mail_ids = data[0].split()[-max_mails:]

            for num in reversed(mail_ids):
                typ, msg_data = mail.fetch(num, '(RFC822)')
                msg = email.message_from_bytes(msg_data[0][1])

                subject, encoding = decode_header(msg.get("Subject"))[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or 'utf-8', errors='ignore')
                from_ = msg.get("From")
                date_ = msg.get("Date")

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                            charset = part.get_content_charset() or 'utf-8'
                            body = part.get_payload(decode=True).decode(charset, errors="ignore")
                            break
                else:
                    charset = msg.get_content_charset() or 'utf-8'
                    body = msg.get_payload(decode=True).decode(charset, errors="ignore")

                score = score_message(body, subject)
                importance = "high" if score > 0.6 else "medium" if score > 0.3 else "low"
                date_parsed = email.utils.parsedate_to_datetime(date_).strftime('%Y-%m-%d') if date_ else ""

                mail_data = MailItem(
                    id=num.decode(),
                    subject=subject,
                    sender=from_,
                    date=date_parsed,
                    body=body,
                    importance=importance,
                    score=score,
                    mailbox=account["IMAP_USER"]
                )

                all_messages.append(mail_data)
                log_mail(mail_data.dict())
            mail.logout()
        except Exception as e:
            print(f"Erreur lors de la récupération des mails pour {account['IMAP_USER']}: {e}")
    return all_messages

@app.get("/api/messages", response_model=List[MailItem])
def get_messages():
    # Recherche automatique des comptes IMAP dans les variables d'environnement
    # Format attendu dans .env :
    # IMAP1_HOST=...
    # IMAP1_USER=...
    # IMAP1_PASS=...
    # IMAP2_HOST=...
    # IMAP2_USER=...
    # etc.
    accounts = []
    i = 1
    while True:
        prefix = f"IMAP{i}_"
        user = os.getenv(prefix + "USER")
        host = os.getenv(prefix + "HOST")
        if not user or not host:
            break
        account = {
            "IMAP_HOST": host,
            "IMAP_USER": user,
            "IMAP_PASS": os.getenv(prefix + "PASS"),
            "ACCESS_TOKEN": os.getenv(prefix + "ACCESS_TOKEN"),
            "REFRESH_TOKEN": os.getenv(prefix + "REFRESH_TOKEN"),
        }
        accounts.append(account)
        i += 1
    # Pour compatibilité ascendante, ajoute le compte simple si présent
    if not accounts and os.getenv("IMAP_USER") and os.getenv("IMAP_HOST"):
        accounts.append({
            "IMAP_HOST": os.getenv("IMAP_HOST"),
            "IMAP_USER": os.getenv("IMAP_USER"),
            "IMAP_PASS": os.getenv("IMAP_PASS"),
            "ACCESS_TOKEN": os.getenv("ACCESS_TOKEN"),
            "REFRESH_TOKEN": os.getenv("REFRESH_TOKEN"),
        })
    return fetch_emails_imap(accounts)

class ReplyData(BaseModel):
    mail_id: str
    reply_content: str

@app.post("/api/reply")
def post_reply(data: ReplyData):
    # Ici tu peux implémenter l’envoi de mail si tu veux
    print(f"Réponse au mail {data.mail_id} : {data.reply_content}")
    return {"status": "ok", "message": "Réponse envoyée"}
