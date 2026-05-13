# Synthese des evaluations de francais

Application web legere pour une classe: les eleves creent un compte, saisissent leurs evaluations de francais, consultent leur synthese personnelle, et la professeure voit la classe complete.

## Ce qui est pret pour un usage reel

- comptes eleves independants avec inscription autonome ;
- compte professeure cree au demarrage via variables d'environnement ;
- mots de passe hashes avec PBKDF2 ;
- sessions stockees en base, persistantes entre redemarrages ;
- base PostgreSQL Supabase via `DATABASE_URL` ;
- schema PostgreSQL prive `app_private` pour eviter l'exposition REST/GraphQL du schema `public` ;
- connexion compatible Supabase SSL et pooler Supavisor.

## Lancer en local

Installer les dependances:

```powershell
python -m pip install -r requirements.txt
```

Definir l'URL PostgreSQL, puis lancer l'application:

```powershell
$env:DATABASE_URL="postgresql://user:password@localhost:5432/synthese_francais"
$env:DATABASE_SCHEMA="public"
python app.py
```

Puis ouvrir `http://127.0.0.1:8000`.

Par defaut, le compte professeure local est:

- identifiant: `prof.francais`
- mot de passe: `change-me-before-deploy`

Pour activer les comptes de demonstration locaux:

```powershell
$env:DEMO_MODE="true"
python app.py
```

Comptes demo: `emma.dupont`, `leo.bernard`, `jade.moreau` avec le mot de passe `eleve123`.

## Base Supabase

Dans Supabase, creer un projet puis recuperer une connection string depuis `Connect`.

Pour une app web persistante de type Render, Fly.io ou Railway, utiliser de preference:

- `Session pooler` si l'hebergeur n'a pas d'IPv6 fiable ;
- `Direct connection` si l'hebergeur supporte IPv6 ;
- `Transaction pooler` seulement pour des environnements serverless ou tres ephemeres.

Variables recommandees en production:

```text
DATABASE_URL=postgresql://postgres.PROJECT_REF:YOUR_DB_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
DATABASE_SSLMODE=require
DATABASE_SCHEMA=app_private
COOKIE_SECURE=true
DEMO_MODE=false
ADMIN_USERNAME=prof.francais
ADMIN_FULL_NAME=Professeur de francais
ADMIN_PASSWORD=mot-de-passe-fort
```

L'application cree automatiquement le schema et les tables au demarrage. Si tu preferes les creer manuellement, coller [supabase/schema.sql](C:/Users/gabri/Documents/New%20project/supabase/schema.sql) dans le SQL Editor de Supabase.

## Migrer les donnees SQLite existantes

Lancer d'abord l'application une fois avec `DATABASE_URL` pour creer les tables Supabase, puis executer:

```powershell
$env:DATABASE_URL="postgresql://postgres.PROJECT_REF:YOUR_DB_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres"
$env:DATABASE_SSLMODE="require"
$env:DATABASE_SCHEMA="app_private"
python migrate_sqlite_to_postgres.py
```

Par defaut, le script lit `prototype.sqlite3` dans le dossier du projet. Pour utiliser un autre fichier:

```powershell
$env:PROTOTYPE_DB_PATH="C:\chemin\vers\prototype.sqlite3"
python migrate_sqlite_to_postgres.py
```

## Variables importantes

- `DATABASE_URL`: URL de connexion PostgreSQL Supabase, obligatoire
- `DATABASE_SSLMODE`: mode SSL, `require` recommande pour Supabase
- `DATABASE_SCHEMA`: schema utilise par l'application, `app_private` recommande sur Supabase
- `ADMIN_USERNAME`: identifiant professeure, par defaut `prof.francais`
- `ADMIN_PASSWORD`: mot de passe initial du compte professeure
- `ADMIN_FULL_NAME`: nom affiche pour le compte professeure
- `COOKIE_SECURE`: `true` en production HTTPS, `false` en local si besoin
- `DEMO_MODE`: `true` uniquement pour creer les comptes de demonstration
- `PROTOTYPE_DB_PATH`: chemin de l'ancienne base SQLite, utilise seulement par le script de migration

## Deploiement Render avec Supabase

Le fichier [render.yaml](C:/Users/gabri/Documents/New%20project/render.yaml) cree uniquement le service web. La base est fournie par Supabase.

Etapes:

1. Creer le projet Supabase.
2. Copier la connection string `Session pooler` depuis Supabase.
3. Pousser ce dossier dans un depot GitHub.
4. Dans Render, creer un Blueprint depuis le depot.
5. Renseigner `DATABASE_URL` et `ADMIN_PASSWORD` dans les variables d'environnement Render.
6. Deployer.
7. Verifier `/healthz`, puis tester une connexion professeure.

## Verification rapide

```powershell
python -m py_compile app.py migrate_sqlite_to_postgres.py
python app.py
```

Tester ensuite:

- creation d'un compte eleve ;
- ajout d'une evaluation ;
- deconnexion/reconnexion ;
- connexion professeure et consultation de la liste des eleves.
