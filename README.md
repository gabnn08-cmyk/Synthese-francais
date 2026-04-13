Hello, c'est gab! Le code a été fait avec codex.



# Prototype de synthèse des évaluations de français

Ce prototype permet :

- à chaque élève de se connecter individuellement ;
- d'ajouter ses notes et appréciations en français ;
- d'obtenir une synthèse automatique de ses forces, faiblesses et axes d'amélioration ;
- à la professeure de consulter une vue individuelle par élève et une synthèse générale de la classe.

## Lancer le prototype

```powershell
python app.py
```

Puis ouvrir `http://127.0.0.1:8000`

## Mise en ligne sur Render

Le projet est prêt pour un déploiement gratuit sur Render avec le fichier [render.yaml](C:/Users/gabri/Documents/New%20project/render.yaml).

1. Créez un dépôt GitHub avec ce dossier.
2. Connectez ce dépôt à votre compte Render.
3. Choisissez le déploiement via `Blueprint`.
4. Validez le service web créé à partir de `render.yaml`.
5. Une URL publique Render sera générée et vous pourrez la transmettre à votre professeure.

Remarque importante :

- la configuration actuelle utilise le plan gratuit `free` ;
- aucun disque persistant n'est monté ;
- la base SQLite est stockée dans un répertoire temporaire du service ;
- les comptes de démonstration sont recréés automatiquement au démarrage ;
- les évaluations ajoutées en ligne peuvent disparaître après un redémarrage, un redéploiement ou une mise en veille du service.

Si vous voulez conserver les données plus tard, il faudra passer à une base persistante, par exemple Render Postgres, ou à une offre avec stockage persistant.

## Comptes de démonstration

- Professeure : `prof.francais` / `demo123`
- Élèves : `emma.dupont`, `leo.bernard`, `jade.moreau` / `eleve123`

## Limites du prototype

- authentification simple pour démonstration ;
- synthèse produite à partir de règles heuristiques ;
- pas encore de suppression ou modification des évaluations ;
- hébergement gratuit possible sur Render, mais stockage non persistant pour l'instant.
