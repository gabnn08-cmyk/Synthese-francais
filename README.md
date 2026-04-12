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

Le projet est prêt pour un déploiement simple sur Render avec le fichier [render.yaml](C:/Users/gabri/Documents/New%20project/render.yaml).

1. Créez un dépôt GitHub avec ce dossier.
2. Connectez ce dépôt à votre compte Render.
3. Choisissez le déploiement via `Blueprint`.
4. Validez le service web créé à partir de `render.yaml`.
5. Une URL publique Render sera générée et vous pourrez la transmettre à votre professeure.

Remarque :

- le fichier `render.yaml` est configuré pour un service `starter` avec disque persistant, car d'après la documentation Render les disques persistants ne sont pas disponibles sur les services web gratuits ;
- le disque persistant permet de conserver la base SQLite entre les redéploiements et redémarrages ;
- si vous voulez absolument rester sur une offre gratuite, il faudra migrer la base vers Render Postgres ou accepter que les données puissent être perdues.

## Comptes de démonstration

- Professeure : `prof.francais` / `demo123`
- Élèves : `emma.dupont`, `leo.bernard`, `jade.moreau` / `eleve123`

## Limites du prototype

- authentification simple pour démonstration ;
- synthèse produite à partir de règles heuristiques ;
- pas encore de suppression ou modification des évaluations ;
- pas d'hébergement distant configuré.
