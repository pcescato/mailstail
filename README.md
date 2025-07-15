# Mail UI - Application de gestion de mails avec scoring intelligent

## Description

Cette application permet de récupérer des mails via IMAP (avec OAuth2 ou mot de passe), de les analyser et scorer automatiquement avec spaCy, puis d’afficher une interface web React/Vite permettant de lire, prioriser et répondre aux mails.

Le backend est développé en FastAPI, exposant une API REST sous `/api/`.  
Le frontend React est servi par Nginx avec un proxy inverse vers le backend.  
L’ensemble est conteneurisé avec Docker et orchestré via `docker-compose`.

---

## Architecture

- **backend/** : backend FastAPI (Python)  
- **frontend/** : frontend React (Vite)  
- **docker-compose.yml** : orchestration Docker pour lancer backend + frontend (Nginx)  
- **.env** : configuration des variables d’environnement (non versionnée)

---

## Installation & usage

### Prérequis

- Docker et Docker Compose installés  
- Accès IMAP valide (ex : Gmail avec OAuth2 ou mot de passe applicatif)

### Configuration

Créer un fichier `.env` à la racine du projet avec les variables nécessaires, par exemple :

```env
IMAP_HOST=imap.gmail.com
IMAP_USER=ton.email@gmail.com
IMAP_PASS=tonmotdepasseappli  # ou laisser vide si OAuth2
CLIENT_ID=ton-client-id-oauth
CLIENT_SECRET=ton-client-secret-oauth
REFRESH_TOKEN=ton-refresh-token-oauth
