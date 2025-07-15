import json
from pathlib import Path

LOGFILE = Path("logs/mail_log.jsonl")

def list_all_mails(logfile):
    if not logfile.exists():
        print("Aucun fichier de log trouvé.")
        return

    with logfile.open(encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                print(f"{data['date']} | {data['importance'].upper():<6} | {data['score']:.2f} | {data['sender']} → {data['subject']}")
            except Exception as e:
                print(f"Erreur de parsing : {e}")

if __name__ == "__main__":
    list_all_mails(LOGFILE)
