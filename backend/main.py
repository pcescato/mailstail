from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import List
import imaplib
import email
import unicodedata
from email.header import decode_header
from html.parser import HTMLParser
import os
import json
import spacy
from dotenv import load_dotenv
import requests

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre en production
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
    mailbox: str  # boîte mail d'origine

NER_WEIGHTS = {
    "ORG": 0.3,
    # fr_core_news_sm émet PER, PERSON est gardé pour les autres modèles
    "PERSON": 0.2,
    "PER": 0.2,
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
    "relance": 0.4,
    "fermeture": 0.4,
    "résiliation": 0.5,
    "suspension": 0.5,
    "échéance": 0.4,
    "expiration": 0.4,
    "impayé": 0.5,
    "dernier rappel": 0.5,
    "alerte de sécurité": 0.4,
    "contrat": 0.2,
    "devis": 0.2
}

# Plafonds par famille : évitent qu'un mail long et bavard sature le score.
ENTITY_SCORE_CAP = 0.4
KEYWORD_SCORE_CAP = 0.6

# Pénalité appliquée aux mails de masse (List-Unsubscribe, Precedence: bulk/list).
BULK_PENALTY = 0.4

# Seuil de lecture spaCy : sujet + N premiers caractères du corps.
SPACY_BODY_MAX_CHARS = 1000

# Seuils de classement par importance.
HIGH_IMPORTANCE_THRESHOLD = 0.6
MEDIUM_IMPORTANCE_THRESHOLD = 0.3

LOG_PATH = "logs/processed_mails.jsonl"
LOGGED_FIELDS = ("timestamp", "id", "mailbox", "sender", "subject", "date", "score", "importance")
_logged_keys = None

def _load_logged_keys() -> set:
    keys = set()
    if not os.path.exists(LOG_PATH):
        return keys
    with open(LOG_PATH, encoding="utf-8") as logfile:
        for line in logfile:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            keys.add((record.get("mailbox"), record.get("id")))
    return keys

def log_mail(data: dict):
    global _logged_keys
    os.makedirs("logs", exist_ok=True)

    record = {k: data[k] for k in LOGGED_FIELDS if k in data}
    if "timestamp" not in record:
        record["timestamp"] = datetime.now(timezone.utc).isoformat()

    if _logged_keys is None:
        _logged_keys = _load_logged_keys()
    key = (record.get("mailbox"), record.get("id"))
    if key in _logged_keys:
        return

    with open(LOG_PATH, "a", encoding="utf-8") as logfile:
        logfile.write(json.dumps(record, ensure_ascii=False) + "\n")
    _logged_keys.add(key)

def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())

def _normalize_entity_text(text: str) -> str:
    return " ".join(text.split()).casefold()

def _is_bulk_mail(headers) -> bool:
    if not headers:
        return False
    hdrs = {str(k).lower(): str(v) for k, v in headers.items()}
    if "list-unsubscribe" in hdrs:
        return True
    precedence = hdrs.get("precedence", "").strip().lower()
    return precedence in ("bulk", "list")

def score_message(body: str, subject: str, headers=None) -> float:
    text = _fold(f"{subject} {body}")
    keyword_score = sum(w for kw, w in KEYWORDS.items() if _fold(kw) in text)

    doc = nlp(subject + "\n" + body[:SPACY_BODY_MAX_CHARS])
    unique_entities = {
        (_normalize_entity_text(ent.text), ent.label_)
        for ent in doc.ents
        if ent.label_ in NER_WEIGHTS
    }
    entity_score = sum(NER_WEIGHTS[label] for _, label in unique_entities)

    score = min(entity_score, ENTITY_SCORE_CAP) + min(keyword_score, KEYWORD_SCORE_CAP)
    if _is_bulk_mail(headers):
        score -= BULK_PENALTY
    return min(max(score, 0.0), 1.0)

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
        access_token = refresh_token()

    if access_token:
        auth_string = f"user={user}\1auth=Bearer {access_token}\1\1"
        mail.authenticate("XOAUTH2", lambda x: auth_string.encode())
    elif password:
        mail.login(user, password)
    else:
        raise HTTPException(status_code=401, detail=f"Aucune méthode d'authentification disponible pour {user}.")

    return mail

SUBJECT_FALLBACK = "(sans objet)"

class _HTMLTextExtractor(HTMLParser):
    BLOCK_TAGS = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table"}
    SKIP_TAGS = {"script", "style", "head", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        elif tag in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self.BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self._chunks.append(data)

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self._chunks).splitlines())
        return "\n".join(line for line in lines if line)

def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text()

def _decode_bytes(raw: bytes, charset) -> str:
    try:
        return raw.decode(charset or "utf-8", errors="ignore")
    except (LookupError, TypeError):
        return raw.decode("utf-8", errors="ignore")

def _part_text(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    return _decode_bytes(payload, part.get_content_charset())

def _decode_header_value(raw, fallback: str = "") -> str:
    if not raw:
        return fallback
    try:
        chunks = []
        for chunk, charset in decode_header(raw):
            if isinstance(chunk, bytes):
                chunk = _decode_bytes(chunk, charset)
            chunks.append(chunk)
        value = "".join(chunks).strip()
    except Exception:
        return fallback
    return value or fallback

def _extract_body(msg) -> str:
    if not msg.is_multipart():
        text = _part_text(msg)
        return _html_to_text(text) if msg.get_content_type() == "text/html" else text

    plain_part = html_part = None
    for part in msg.walk():
        if "attachment" in str(part.get("Content-Disposition")):
            continue
        content_type = part.get_content_type()
        if content_type == "text/plain" and plain_part is None:
            plain_part = part
        elif content_type == "text/html" and html_part is None:
            html_part = part

    text = _part_text(plain_part) if plain_part is not None else ""
    if text.strip() or html_part is None:
        return text
    return _html_to_text(_part_text(html_part))

def fetch_emails_imap(accounts, mailbox="INBOX", max_mails=10):
    all_messages = []
    for account in accounts:
        try:
            mail = connect_imap(account)
            mail.select(mailbox)
            typ, data = mail.search(None, 'ALL')
            mail_ids = data[0].split()[-max_mails:]

            for num in reversed(mail_ids):
                try:
                    typ, msg_data = mail.fetch(num, '(RFC822)')
                    msg = email.message_from_bytes(msg_data[0][1])

                    subject = _decode_header_value(msg.get("Subject"), SUBJECT_FALLBACK)
                    from_ = _decode_header_value(msg.get("From"), "")
                    date_ = msg.get("Date")
                    body = _extract_body(msg)

                    score = score_message(body, subject, headers=msg)
                    importance = "high" if score > HIGH_IMPORTANCE_THRESHOLD else "medium" if score > MEDIUM_IMPORTANCE_THRESHOLD else "low"
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
                except Exception as e:
                    print(f"Erreur sur le mail id={num.decode(errors='replace')} ({account['IMAP_USER']}): {e}")
            mail.logout()
        except Exception as e:
            print(f"Erreur lors de la récupération des mails pour {account['IMAP_USER']}: {e}")
    return all_messages

@app.get("/api/messages", response_model=List[MailItem])
def get_messages():
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
    # Exemple : implémentation à venir
    print(f"Réponse au mail {data.mail_id} : {data.reply_content}")
    return {"status": "ok", "message": "Réponse envoyée"}
