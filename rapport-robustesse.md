# Rapport : robustesse de `fetch_emails_imap()`

## Problèmes corrigés

1. **Sujet absent** : `decode_header(None)` levait une exception qui faisait échouer tout le compte. Désormais, un sujet absent, vide ou illisible donne `"(sans objet)"`.
2. **Mail HTML seul** : seule la première partie `text/plain` était lue, donc un mail HTML sans partie texte sortait avec un corps vide. Désormais, si aucune partie `text/plain` non vide n'existe, on repli sur `text/html` converti en texte brut.
3. **Payload `None`** : `get_payload(decode=True)` pouvait renvoyer `None` et faire planter le `.decode()`. Désormais, il renvoie `""`.
4. **Isolement par mail** : chaque mail a son propre `try/except`. Une erreur est affichée avec l'id du mail et le compte, et les autres mails sont traités.

## Changements (`backend/main.py`, uniquement)

- Import `from html.parser import HTMLParser` (bibliothèque standard, pas de nouvelle dépendance).
- Nouvelles fonctions et constante, placées juste avant `fetch_emails_imap` :
  - `SUBJECT_FALLBACK = "(sans objet)"`
  - `_HTMLTextExtractor` / `_html_to_text` : ignore `script`, `style`, `head`, `title` ; saute une ligne sur les balises de bloc ; décode les entités HTML (`convert_charrefs=True`).
  - `_decode_bytes` : décodage avec repli sur UTF-8 si le charset est inconnu (`LookupError`).
  - `_part_text` : renvoie `""` si le payload est `None`.
  - `_decode_subject` : décode toutes les parties RFC 2047 et les assemble.
  - `_extract_body` : prend le premier `text/plain` non joint ; sinon le premier `text/html` converti. Les pièces jointes sont ignorées comme avant.
- `fetch_emails_imap` : la boucle par mail est dans un `try/except` qui affiche `Erreur sur le mail id=... (compte)`. Le `try/except` du compte reste pour les erreurs de connexion.
- `from_ = msg.get("From") or ""` : un mail sans `From` ne fait plus échouer la validation de `MailItem.sender: str`.

Non modifiés : `MailItem`, la route `/api/messages`, le frontend, les dépendances, et aucune connexion IMAP n'a été lancée.

## Comportements à connaître

- **Sujet multi-parties** : l'ancien code ne gardait que la première partie RFC 2047. Le nouveau code les assemble toutes, donc un sujet encodé en plusieurs morceaux s'affiche complet.
- **Repli HTML** : le repli n'a lieu que si le `text/plain` est absent ou vide après décodage. Un `text/plain` non vide reste prioritaire.
- **Mail défectueux** : il est sauté et ignoré dans la liste retournée, avec un message dans les logs. Il n'est pas inclus avec un corps vide.
- **Connexion coupée en cours de boucle** : chaque mail qui échoue produit son propre message. C'est voulu, mais cela peut faire beaucoup de lignes si la connexion tombe.

## Cas limites couverts (vérifiés)

| Cas | Résultat |
|---|---|
| Sujet `None` | `(sans objet)` |
| Sujet vide | `(sans objet)` |
| Sujet encodé RFC 2047 (`Facture été`) | décodé correctement |
| Charset inconnu dans le sujet | repli sans exception |
| HTML seul, avec `<style>`, `<script>`, `&amp;` | texte propre, `Bonjour & Paris` |
| HTML non multipart | converti |
| `text/plain` non vide + `text/html` | `text/plain` gagne |
| Multipart sans contenu décodable (payload `None`) | `""` |
| Réponse IMAP défectueuse au milieu d'un lot | ce mail est sauté, les deux autres sont gardés |
| Mail sans `Subject` ni `From` | gardé, `sender=""` |

## Comment tester

Test réalisé dans un venv temporaire supprimé ensuite, avec un faux client IMAP (`connect_imap` remplacé). Aucune connexion réelle.

- Vérifier la syntaxe : `python -m py_compile backend/main.py`.
- Pour reproduire le test, importer `main` depuis `backend/`, appeler `_decode_subject`, `_extract_body`, puis `fetch_emails_imap` avec un `connect_imap` simulé qui renvoie un mail défectueux au milieu.
- Attendu : le mail défectueux produit une ligne `Erreur sur le mail id=...`, les autres sont retournés.

Rien n'a été commité.
