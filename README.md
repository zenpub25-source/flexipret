# 🏦 FlexiPrêt — Site de prêt avec back-end Flask + SQLite

## Structure du projet

```
flexipret/
├── app.py          # Serveur Flask + API REST
├── index.html      # Site web (front-end)
├── flexipret.db    # Base de données SQLite (créée automatiquement)
├── README.md       # Ce fichier
└── requirements.txt
```

---

## ⚡ Installation & Lancement

### 1. Prérequis
- Python 3.8+
- pip

### 2. Installer les dépendances
```bash
pip install flask
```

### 3. Lancer le serveur
```bash
python3 app.py
```

Vous devriez voir :
```
✅ Base de données initialisée : flexipret.db
🚀 FlexiPrêt API démarrée sur http://localhost:5000
📖 Documentation API : http://localhost:5000/api
```

### 4. Ouvrir le site
Ouvrez `index.html` dans votre navigateur.
Le site se connecte automatiquement à `http://localhost:5000`.

---

## 🗄️ Base de données SQLite

La base `flexipret.db` est créée automatiquement au premier lancement.

### Tables

#### `demandes`
| Colonne      | Type    | Description                              |
|-------------|---------|------------------------------------------|
| id          | INTEGER | Clé primaire auto-incrémentée            |
| prenom      | TEXT    | Prénom du demandeur                      |
| nom         | TEXT    | Nom du demandeur                         |
| email       | TEXT    | Email de contact                         |
| telephone   | TEXT    | Numéro de téléphone (optionnel)          |
| montant     | REAL    | Montant du prêt demandé (€)              |
| duree       | INTEGER | Durée en mois                            |
| type_pret   | TEXT    | Type de prêt                             |
| revenus     | REAL    | Revenus mensuels nets (optionnel)        |
| situation   | TEXT    | Situation professionnelle (optionnel)    |
| statut      | TEXT    | en-cours / approuve / refuse / rembourse |
| note        | TEXT    | Note du conseiller                       |
| created_at  | TEXT    | Date de création                         |
| updated_at  | TEXT    | Date de dernière modification            |

#### `historique`
Trace toutes les actions effectuées sur chaque demande (création, changement de statut…).

#### `utilisateurs`
Conseillers et administrateurs de la plateforme.

---

## 🔌 API REST — Endpoints

| Méthode | Route                          | Description                          |
|---------|--------------------------------|--------------------------------------|
| GET     | `/api`                         | Documentation de l'API               |
| GET     | `/api/demandes`                | Lister toutes les demandes           |
| GET     | `/api/demandes?statut=X`       | Filtrer par statut                   |
| POST    | `/api/demandes`                | Créer une nouvelle demande           |
| GET     | `/api/demandes/:id`            | Détail + historique d'une demande    |
| PUT     | `/api/demandes/:id/statut`     | Changer le statut (+ note)           |
| DELETE  | `/api/demandes/:id`            | Supprimer une demande                |
| GET     | `/api/stats`                   | Statistiques globales                |
| GET     | `/api/export/csv`              | Télécharger toutes les demandes CSV  |
| GET     | `/api/utilisateurs`            | Lister les conseillers               |
| POST    | `/api/utilisateurs`            | Créer un conseiller                  |
| GET     | `/api/historique`              | Journal des 100 dernières actions    |

### Exemples de requêtes

**Créer une demande :**
```bash
curl -X POST http://localhost:5000/api/demandes \
  -H "Content-Type: application/json" \
  -d '{
    "prenom": "Marie",
    "nom": "Dupont",
    "email": "marie@email.com",
    "montant": 15000,
    "duree": 48,
    "type_pret": "Prêt confort",
    "revenus": 3200,
    "situation": "CDI"
  }'
```

**Approuver une demande :**
```bash
curl -X PUT http://localhost:5000/api/demandes/1/statut \
  -H "Content-Type: application/json" \
  -d '{"statut": "approuve", "note": "Profil solide, CDI confirmé"}'
```

**Statistiques :**
```bash
curl http://localhost:5000/api/stats
```

**Export CSV :**
```bash
curl http://localhost:5000/api/export/csv -o export.csv
```

---

## 🌐 Pour mettre en production

Pour déployer sur un vrai serveur :

1. **Remplacez SQLite par PostgreSQL** via `psycopg2`
2. **Utilisez Gunicorn** au lieu du serveur de développement Flask :
   ```bash
   pip install gunicorn
   gunicorn -w 4 app:app
   ```
3. **Ajoutez Nginx** en reverse proxy
4. **Hébergement** : Railway, Render, DigitalOcean, OVH VPS…

---

## 📋 requirements.txt
```
flask>=3.0.0
```
