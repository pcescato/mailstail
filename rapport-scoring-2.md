# Rapport : scoring, deuxième passe

## Changements (`backend/main.py`, uniquement)

1. **Label `PER`** : `NER_WEIGHTS` contient maintenant `"PER": 0.2` à côté de `"PERSON": 0.2`. `fr_core_news_sm` émet `PER`, donc le poids des personnes est enfin appliqué. Avant, il était ignoré : `Bonjour Jean Dupont.` donnait 0.0, il donne maintenant 0.4.

2. **Mots-clés** : dix entrées ajoutées à `KEYWORDS` (fermeture 0.4, résiliation 0.5, suspension 0.5, échéance 0.4, expiration 0.4, impayé 0.5, dernier rappel 0.5, alerte de sécurité 0.4, contrat 0.2, devis 0.2).
   - Nouvelle fonction `_fold()` : NFKD, suppression des marques combinantes, `casefold()`, espaces compactés. Elle s'applique au texte du mail et aux mots-clés, donc `echeance`, `Échéance` et `ÉCHÉANCE` matchent.
   - `KEYWORD_SCORE_CAP` (0.6), `ENTITY_SCORE_CAP` (0.4), `BULK_PENALTY` et les seuils 0.6 / 0.3 sont inchangés.
   - Aucune dépendance ajoutée (`unicodedata` est dans la bibliothèque standard).

3. **Expéditeur** : `_decode_subject` est remplacé par `_decode_header_value(raw, fallback)`, utilisé pour le sujet (fallback `(sans objet)`) et pour `From` (fallback `""`). Même décodage RFC 2047, avec repli si le charset est inconnu.

`MailItem`, la route `/api/messages`, le frontend et les dépendances ne sont pas touchés. Aucune connexion IMAP.

## Scores des exemples synthétiques

Ces scores viennent de `score_message()` lancé dans un venv temporaire (spaCy `fr_core_news_sm` 3.8.0).

| Exemple | Score | Importance |
|---|---|---|
| « Demande de fermeture de services », corps avec « fermeture », « hébergement », « Jean Dupont » | **0.8** | high |
| Newsletter avec `List-Unsubscribe` (30 répétitions de phrases avec Google, Paris, Renault) | **0.0** | low |
| Même newsletter sans en-tête de masse | 0.4 | medium |
| « Point projet », sans mot-clé, avec Google et Paris | 0.4 | medium |
| « echeance » sans accent vs « Échéance » | match dans les deux cas (même contribution de 0.4) | |
| `Bonjour Jean Dupont.` vs `Bonjour.` | 0.4 vs 0.0 (poids `PER` actif) | |

Décodage de `From` :
- `=?UTF-8?q?=22Cit=C3=A9_Scolaire=22_via_PRONOTE?= <notification@pronote.fr>` devient `"Cité Scolaire" via PRONOTE <notification@pronote.fr>`.
- Un `From` mixte (`=?UTF-8?q?Jean?= =?UTF-8?q?_Dupont?= <j@x.fr>`) devient `Jean Dupont <j@x.fr>`.
- `From` absent donne `""`.

Le test « fermeture de services » est le seul des trois qui atteint `high` (0.8). Un mail sans mot-clé plafonne à 0.4 (entités seules), ce qui est voulu : un mail sans signal fort ne doit pas passer en `high`.

## Effets de bord

- **Recherche par sous-chaîne** : la correspondance reste une sous-chaîne, comme avant. Donc `devis` matche « devise », `contrat` matche « contrats », `fermeture` matche « fermeture exceptionnelle du magasin » dans une newsletter. Un mot-clé très courant peut donc faire monter un mail à tort. Une correspondance par mot entier (`\b`) réglerait ça, mais elle changerait aussi `relance` vs `relances`. Non traité ici.
- **Newsletters** : une newsletter qui parle de « fermeture » ou « contrat » gagne 0.2 à 0.4. Sans `List-Unsubscribe`, elle peut donc atteindre `medium`. La pénalité de masse reste le filet principal.
- **Espaces** : `_fold()` compacte les espaces, donc « dernier\nrappel » matche maintenant « dernier rappel ». C'est un effet positif, mais il élargit légèrement la détection.
- **Hausse générale des scores** : l'activation du poids `PER` ajoute 0.2 à tout mail contenant un nom de personne, ce qui fait monter une partie du corpus. Attendu, mais à surveiller.
- **Sujet** : son décodage passe par le même helper, le résultat pour les sujets déjà décodés est identique à la passe précédente (`Facture été`).
- **Modèle** : les entités dépendent du modèle installé (`md` ou `sm`). Une différence d'accent peut changer la détection d'entités (ex. « Votre » classé LOC sans accent), ce qui décale le score d'autant. La correspondance des mots-clés, elle, est identique.

Rien n'a été commité.
