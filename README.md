# Synthèse des évaluations de français

Application web légère pour une classe: les élèves créent un compte, saisissent leurs évaluations de français, consultent leur synthèse personnelle, et la professeure ou l'administrateur voit la classe complète.

## Ce qui est prêt pour un usage réel

- comptes élèves indépendants avec inscription autonome ;
- comptes administrateur et professeure distincts, créés au démarrage via variables d'environnement ;
- mots de passe hashes avec PBKDF2 ;
- sessions stockées en base, persistantes entre redémarrages ;
- base PostgreSQL Supabase via `DATABASE_URL` ;
- schéma PostgreSQL privé `app_private` pour éviter l'exposition REST/GraphQL du schéma `public` ;
- connexion compatible Supabase SSL et pooler Supavisor.

## Lancer en local

Installer les dépendances:

```powershell
python -m pip install -r requirements.txt
```

Définir l'URL PostgreSQL, puis lancer l'application:

```powershell
$env:DATABASE_URL="postgresql://user:password@localhost:5432/synthese_francais"
$env:DATABASE_SCHEMA="public"
$env:ADMIN_PASSWORD="change-me-before-deploy"
$env:TEACHER_PASSWORD="change-me-before-deploy-too"
python app.py
```

Puis ouvrir `http://127.0.0.1:8000`.

Par défaut, les comptes locaux sont:

- administrateur: identifiant `admin`, mot de passe `ADMIN_PASSWORD`
- professeure: identifiant `prof.francais`, mot de passe `TEACHER_PASSWORD` si défini, sinon `ADMIN_PASSWORD`

Pour activer les comptes de démonstration locaux:

```powershell
$env:DEMO_MODE="true"
python app.py
```

Comptes démo: `emma.dupont`, `leo.bernard`, `jade.moreau` avec le mot de passe `eleve123`.

## Base Supabase

Dans Supabase, créer un projet puis récupérer une connection string depuis `Connect`.

Pour une app web persistante de type Render, Fly.io ou Railway, utiliser de préférence:

- `Session pooler` si l'hébergeur n'a pas d'IPv6 fiable ;
- `Direct connection` si l'hébergeur supporte IPv6 ;
- `Transaction pooler` seulement pour des environnements serverless ou très éphémères.

Variables recommandées en production:

```text
DATABASE_URL=postgresql://postgres.PROJECT_REF:YOUR_DB_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
DATABASE_SSLMODE=require
DATABASE_SCHEMA=app_private
COOKIE_SECURE=true
DEMO_MODE=false
SITE_NAME=Synthese de francais
SITE_URL=https://votre-domaine.fr
LEGAL_ENTITY_NAME=Nom de l'etablissement ou de l'organisme
LEGAL_ENTITY_STATUS=Etablissement scolaire
LEGAL_ENTITY_ADDRESS=Adresse postale complete
LEGAL_CONTACT_EMAIL=contact@votre-domaine.fr
LEGAL_CONTACT_PHONE=0102030405
LEGAL_PUBLICATION_DIRECTOR=Nom du responsable de publication
LEGAL_DPO_CONTACT=rgpd@votre-domaine.fr
HOSTING_PROVIDER_NAME=Nom de l'hebergeur
HOSTING_PROVIDER_ADDRESS=Adresse de l'hebergeur
HOSTING_PROVIDER_PHONE=Telephone de l'hebergeur
PRIVACY_ACCOUNT_RETENTION=jusqu'a 12 mois apres la derniere activite du compte
PRIVACY_EVALUATION_RETENTION=pendant l'annee scolaire en cours puis selon la politique de l'etablissement
ACCESSIBILITY_CONTACT=accessibilite@votre-domaine.fr
ACCESSIBILITY_MULTIYEAR_PLAN_URL=https://votre-domaine.fr/accessibilite-plan
ADMIN_USERNAME=admin
ADMIN_FULL_NAME=Administrateur
ADMIN_PASSWORD=mot-de-passe-fort
TEACHER_USERNAME=prof.francais
TEACHER_FULL_NAME=Professeur de français
TEACHER_PASSWORD=autre-mot-de-passe-fort
```

L'application crée automatiquement le schéma et les tables au démarrage. Si tu préfères les créer manuellement, coller [supabase/schema.sql](C:/Users/gabri/Documents/New%20project/supabase/schema.sql) dans le SQL Editor de Supabase.

## Migrer les données SQLite existantes

Lancer d'abord l'application une fois avec `DATABASE_URL` pour créer les tables Supabase, puis exécuter:

```powershell
$env:DATABASE_URL="postgresql://postgres.PROJECT_REF:YOUR_DB_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres"
$env:DATABASE_SSLMODE="require"
$env:DATABASE_SCHEMA="app_private"
python migrate_sqlite_to_postgres.py
```

Par défaut, le script lit `prototype.sqlite3` dans le dossier du projet. Pour utiliser un autre fichier:

```powershell
$env:PROTOTYPE_DB_PATH="C:\chemin\vers\prototype.sqlite3"
python migrate_sqlite_to_postgres.py
```

## Variables importantes

- `DATABASE_URL`: URL de connexion PostgreSQL Supabase, obligatoire
- `DATABASE_SSLMODE`: mode SSL, `require` recommande pour Supabase
- `DATABASE_SCHEMA`: schéma utilisé par l'application, `app_private` recommandé sur Supabase
- `ADMIN_USERNAME`: identifiant administrateur, par défaut `admin`
- `ADMIN_PASSWORD`: mot de passe initial du compte administrateur
- `ADMIN_FULL_NAME`: nom affiché pour le compte administrateur
- `TEACHER_USERNAME`: identifiant professeure, par défaut `prof.francais`
- `TEACHER_PASSWORD`: mot de passe initial du compte professeure, par défaut identique à `ADMIN_PASSWORD` si absent
- `TEACHER_FULL_NAME`: nom affiché pour le compte professeure
- `COOKIE_SECURE`: `true` en production HTTPS, `false` en local si besoin
- `DEMO_MODE`: `true` uniquement pour creer les comptes de demonstration
- `PROTOTYPE_DB_PATH`: chemin de l'ancienne base SQLite, utilise seulement par le script de migration
- `SITE_NAME`, `SITE_URL`: nom public du service et URL de deploiement
- `LEGAL_*`: informations d'editeur, de contact, de responsable de publication et de point RGPD affichees sur les pages legales
- `HOSTING_PROVIDER_*`: informations d'hebergement affichees dans les mentions legales
- `PRIVACY_*`: durees de conservation affichees dans la politique de confidentialite
- `ACCESSIBILITY_CONTACT`, `ACCESSIBILITY_MULTIYEAR_PLAN_URL`: contact et lien de reference pour la page accessibilite

## Déploiement Render avec Supabase

Le fichier [render.yaml](C:/Users/gabri/Documents/New%20project/render.yaml) crée uniquement le service web. La base est fournie par Supabase.

Étapes:

1. Créer le projet Supabase.
2. Copier la connection string `Session pooler` depuis Supabase.
3. Pousser ce dossier dans un dépôt GitHub.
4. Dans Render, créer un Blueprint depuis le dépôt.
5. Renseigner `DATABASE_URL`, `ADMIN_PASSWORD` et `TEACHER_PASSWORD` dans les variables d'environnement Render.
6. Déployer.
7. Vérifier `/healthz`, puis tester une connexion professeure.

## Vérification rapide

```powershell
python -m py_compile app.py migrate_sqlite_to_postgres.py
python app.py
```

Tester ensuite:

- création d'un compte élève ;
- ajout d'une évaluation ;
- déconnexion/reconnexion ;
- connexion professeure et consultation de la liste des élèves ;
- connexion administrateur avec un compte distinct.
