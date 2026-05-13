# Synthese des evaluations de francais

Application web legere pour une classe: les eleves creent un compte, saisissent leurs evaluations de francais, consultent leur synthese personnelle, et la professeure voit la classe complete.

## Ce qui est pret pour un usage reel

- comptes eleves independants avec inscription autonome ;
- compte professeure cree au demarrage via variables d'environnement ;
- mots de passe hashes avec PBKDF2 ;
- sessions stockees en base, persistantes entre redemarrages ;
- base SQLite en mode WAL avec verrou d'ecriture applicatif ;
- donnees utilisateur echappees cote navigateur avant affichage ;
- configuration Render avec disque persistant.

Cette architecture est suffisante pour une classe d'environ 40 utilisateurs qui saisissent des evaluations ponctuellement. Pour plusieurs classes ou une utilisation intensive, il faudra passer sur PostgreSQL et un serveur applicatif WSGI/ASGI.

## Lancer en local

```powershell
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

## Variables importantes

- `ADMIN_USERNAME`: identifiant professeure, par defaut `prof.francais`
- `ADMIN_PASSWORD`: mot de passe initial du compte professeure
- `ADMIN_FULL_NAME`: nom affiche pour le compte professeure
- `DATA_DIR`: dossier de stockage de `prototype.sqlite3`
- `COOKIE_SECURE`: `true` en production HTTPS, `false` en local si besoin
- `DEMO_MODE`: `true` uniquement pour creer les comptes de demonstration

## Deploiement Render

Le fichier [render.yaml](C:/Users/gabri/Documents/New%20project/render.yaml) cree:

- un service web Python en region Frankfurt ;
- un disque persistant de 1 Go monte dans `/var/data` ;
- les variables necessaires au stockage et aux cookies HTTPS.

Etapes:

1. Pousser ce dossier dans un depot GitHub.
2. Dans Render, creer un Blueprint depuis le depot.
3. Renseigner `ADMIN_PASSWORD` dans les variables d'environnement Render.
4. Deployer.
5. Transmettre l'URL aux eleves pour qu'ils creent leur compte.

Important: le plan `starter` est volontaire. Le plan gratuit ne garantit pas un stockage persistant adapte a un usage de classe.

## Verification rapide

```powershell
python -m py_compile app.py
python app.py
```

Tester ensuite:

- creation d'un compte eleve ;
- ajout d'une evaluation ;
- deconnexion/reconnexion ;
- connexion professeure et consultation de la liste des eleves.
