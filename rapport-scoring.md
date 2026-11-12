# Rapport : correction du scoring des mails (`score_message`)

## Problème

`score_message()` additionnait le poids de chaque occurrence d'entité spaCy, sans dédoublonnage, puis plafonnait le total à 1.0. Un mail long (newsletter, relevé, etc.) contient beaucoup d'occurrences et saturait donc à 1.0 / `high`. Le score mesurait la longueur, pas l'importance.

## Changements (`backend/main.py`, uniquement)

1. **Constantes nommées** en haut du fichier, après `KEYWORDS` :
   - `ENTITY_SCORE_CAP = 0.4`, `KEYWORD_SCORE_CAP = 0.6`
   - `BULK_PENALTY = 0.4`
   - `SPACY_BODY_MAX_CHARS = 1000`
   - `HIGH_IMPORTANCE_THRESHOLD = 0.6`, `MEDIUM_IMPORTANCE_THRESHOLD = 0.3`
2. **Dédoublonnage des entités** : clé `(texte normalisé, label)` où la normalisation fait `casefold()` et compacte les espaces. Une même entité ne compte qu'une fois.
3. **Plafonds séparés** : contribution des entités plafonnée à 0.4, celle des mots-clés à 0.6. Le total est ensuite borné dans `[0, 1]`.
4. **spaCy** ne reçoit que le sujet + les 1000 premiers caractères du corps.
5. **Pénalité de masse** : `List-Unsubscribe` présent, ou `Precedence` valant `bulk` / `list` (insensible à la casse et aux espaces), retire 0.4, plancher à 0. Pas de critère `no-reply`.
6. **En-têtes** : `score_message(body, subject, headers=None)`. Le paramètre est optionnel, donc l'appel à deux arguments reste valide. `fetch_emails_imap` passe `headers=msg`. Les en-têtes sont normalisés en minuscules, donc un `email.message.Message` comme un `dict` fonctionnent.
7. Les seuils `0.6 / 0.3` de `fetch_emails_imap` sont remplacés par les constantes. Le comportement ne change pas.

Non modifiés : `MailItem`, la route `/api/messages`, le frontend, les dépendances.

## Valeurs choisies

- **Plafond entités 0.4 / mots-clés 0.6** : les entités servent d'indice de contenu, les mots-clés (`urgent`, `mise en demeure`) sont plus directs. Avec ces plafonds, un mail sans signal fort reste sous 0.4 et l'importance « high » exige un vrai mot-clé.
- **Pénalité 0.4** : un mail de masse avec de bons indices (0.4 à 0.6) tombe en `low` ou `medium`, sans être effacé.
- **1000 caractères** : le début d'un mail porte l'essentiel du sens et borne le coût de spaCy.

## Comment vérifier

Test réalisé dans un venv temporaire (`/tmp`), spaCy (version non épinglée de `backend/requirements.txt`) et `fr_core_news_sm` 3.8.0. Rien n'a été installé dans le projet et aucune connexion IMAP n'a été faite.

- Une newsletter de ~40 répétitions d'une phrase avec entités : **0.4** sans en-tête, **0.0** avec `List-Unsubscribe`.
- Une entité unique citée 1 fois ou 40 fois : **0.4 dans les deux cas** (dédoublonnage).
- Une alerte de sécurité `no-reply` sans en-tête de masse : même score qu'avec `headers={}`.
- Mots-clés seuls très chargés : **0.6** (plafond).
- Pénalité sur un mail à score nul : **0.0** (plancher).
- Tous les scores restent dans `[0, 1]`.

Reproduire : `python -m py_compile backend/main.py`, puis appeler `score_message` depuis un shell Python avec le modèle spaCy installé.

## Points à connaître (non corrigés, hors périmètre)

- **Label `PER` vs `PERSON`** : le modèle `fr_core_news_sm` émet `PER`, alors que `NER_WEIGHTS` ne contient que `PERSON`. Le poids des personnes n'est donc jamais appliqué. C'est un bug préexistant, je ne l'ai pas corrigé car tu as demandé de ne toucher qu'à ce qui concerne le scoring demandé. Le corriger changera les scores.
- **Saturation possible** : 0.4 + 0.6 = 1.0. Un mail qui atteint les deux plafonds reste à 1.0. Pour l'éviter, baisser un des plafonds ou réduire les poids.
- **Mots-clés** : ils sont toujours cherchés dans le corps complet, pas dans les 1000 premiers caractères. Seul spaCy est limité, comme demandé.
- **Modèle `sm` vs `md`** : `score_message` charge `fr_core_news_md` si disponible, sinon `sm`. Les résultats peuvent différer selon le modèle installé.

Rien n'a été commité.
