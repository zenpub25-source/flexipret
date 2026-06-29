"""
FlexiPrêt — Back-end Flask + SQLite
Prod : gunicorn app:app --bind 0.0.0.0:$PORT
Dev  : python3 app.py
"""

import os
import sqlite3
import json
import csv
import io
from datetime import datetime
from flask import Flask, request, jsonify, g, send_file, send_from_directory

app = Flask(__name__, static_folder=".", static_url_path="")

# SQLite stocké dans /tmp sur Railway (éphémère) — pour prod sérieuse, migrer vers PostgreSQL
DB_PATH = os.environ.get("DB_PATH", "flexipret.db")

# ──────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    return response

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return jsonify({}), 200

# ──────────────────────────────────────────────
# SERVE FRONTEND
# ──────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# ──────────────────────────────────────────────
# DATABASE
# ──────────────────────────────────────────────
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS demandes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            prenom      TEXT NOT NULL,
            nom         TEXT NOT NULL,
            email       TEXT NOT NULL,
            telephone   TEXT,
            montant     REAL NOT NULL,
            duree       INTEGER NOT NULL,
            type_pret   TEXT NOT NULL,
            revenus     REAL,
            situation   TEXT,
            statut      TEXT DEFAULT 'en-cours',
            note        TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            updated_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS historique (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            demande_id  INTEGER NOT NULL,
            action      TEXT NOT NULL,
            details     TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(demande_id) REFERENCES demandes(id)
        );

        CREATE TABLE IF NOT EXISTS utilisateurs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nom         TEXT NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            role        TEXT DEFAULT 'conseiller',
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        );

        INSERT OR IGNORE INTO utilisateurs (nom, email, role)
        VALUES ('Admin FlexiPrêt', 'admin@flexipret.fr', 'admin');
        """)
    print(f"✅ Base de données prête : {DB_PATH}")

# ──────────────────────────────────────────────
# API — DEMANDES
# ──────────────────────────────────────────────
@app.route("/api/demandes", methods=["GET"])
def get_demandes():
    db = get_db()
    statut = request.args.get("statut")
    if statut:
        rows = db.execute(
            "SELECT * FROM demandes WHERE statut=? ORDER BY created_at DESC", (statut,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM demandes ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/demandes/<int:did>", methods=["GET"])
def get_demande(did):
    db = get_db()
    row = db.execute("SELECT * FROM demandes WHERE id=?", (did,)).fetchone()
    if not row:
        return jsonify({"error": "Demande introuvable"}), 404
    hist = db.execute(
        "SELECT * FROM historique WHERE demande_id=? ORDER BY created_at DESC", (did,)
    ).fetchall()
    result = dict(row)
    result["historique"] = [dict(h) for h in hist]
    return jsonify(result)


@app.route("/api/demandes", methods=["POST"])
def create_demande():
    data = request.get_json(force=True)
    required = ["prenom", "nom", "email", "montant", "duree", "type_pret"]
    for f in required:
        if not data.get(f):
            return jsonify({"error": f"Champ requis manquant : {f}"}), 400
    db = get_db()
    cur = db.execute(
        """INSERT INTO demandes
           (prenom, nom, email, telephone, montant, duree, type_pret, revenus, situation)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            data["prenom"], data["nom"], data["email"],
            data.get("telephone"), float(data["montant"]),
            int(data["duree"]), data["type_pret"],
            float(data["revenus"]) if data.get("revenus") else None,
            data.get("situation"),
        ),
    )
    db.execute(
        "INSERT INTO historique (demande_id, action, details) VALUES (?,?,?)",
        (cur.lastrowid, "creation", "Demande soumise via le formulaire en ligne"),
    )
    db.commit()
    new = db.execute("SELECT * FROM demandes WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(new)), 201


@app.route("/api/demandes/<int:did>/statut", methods=["PUT"])
def update_statut(did):
    data = request.get_json(force=True)
    nouveau_statut = data.get("statut")
    valides = ("en-cours", "approuve", "refuse", "rembourse")
    if nouveau_statut not in valides:
        return jsonify({"error": f"Statut invalide. Valeurs : {valides}"}), 400
    db = get_db()
    if not db.execute("SELECT id FROM demandes WHERE id=?", (did,)).fetchone():
        return jsonify({"error": "Demande introuvable"}), 404
    db.execute(
        "UPDATE demandes SET statut=?, note=?, updated_at=datetime('now','localtime') WHERE id=?",
        (nouveau_statut, data.get("note", ""), did),
    )
    db.execute(
        "INSERT INTO historique (demande_id, action, details) VALUES (?,?,?)",
        (did, f"statut→{nouveau_statut}", data.get("note", "")),
    )
    db.commit()
    updated = db.execute("SELECT * FROM demandes WHERE id=?", (did,)).fetchone()
    return jsonify(dict(updated))


@app.route("/api/demandes/<int:did>", methods=["DELETE"])
def delete_demande(did):
    db = get_db()
    if not db.execute("SELECT id FROM demandes WHERE id=?", (did,)).fetchone():
        return jsonify({"error": "Demande introuvable"}), 404
    db.execute("DELETE FROM historique WHERE demande_id=?", (did,))
    db.execute("DELETE FROM demandes WHERE id=?", (did,))
    db.commit()
    return jsonify({"message": f"Demande #{did} supprimée"})


# ──────────────────────────────────────────────
# API — STATS
# ──────────────────────────────────────────────
@app.route("/api/stats", methods=["GET"])
def get_stats():
    db = get_db()
    total      = db.execute("SELECT COUNT(*) FROM demandes").fetchone()[0]
    approuves  = db.execute("SELECT COUNT(*) FROM demandes WHERE statut='approuve'").fetchone()[0]
    refuses    = db.execute("SELECT COUNT(*) FROM demandes WHERE statut='refuse'").fetchone()[0]
    en_cours   = db.execute("SELECT COUNT(*) FROM demandes WHERE statut='en-cours'").fetchone()[0]
    rembourses = db.execute("SELECT COUNT(*) FROM demandes WHERE statut='rembourse'").fetchone()[0]
    avg_row    = db.execute("SELECT AVG(montant) FROM demandes").fetchone()[0]
    total_m    = db.execute("SELECT SUM(montant) FROM demandes").fetchone()[0]
    avg_app    = db.execute("SELECT AVG(montant) FROM demandes WHERE statut='approuve'").fetchone()[0]
    types      = db.execute(
        "SELECT type_pret, COUNT(*) as n, SUM(montant) as total FROM demandes GROUP BY type_pret"
    ).fetchall()
    par_mois   = db.execute(
        """SELECT strftime('%Y-%m', created_at) as mois, COUNT(*) as n, SUM(montant) as total
           FROM demandes GROUP BY mois ORDER BY mois DESC LIMIT 12"""
    ).fetchall()
    return jsonify({
        "total": total, "approuves": approuves, "refuses": refuses,
        "en_cours": en_cours, "rembourses": rembourses,
        "montant_moyen": round(avg_row, 2) if avg_row else 0,
        "montant_total": round(total_m, 2) if total_m else 0,
        "montant_moyen_approuve": round(avg_app, 2) if avg_app else 0,
        "taux_approbation": round(approuves / total * 100, 1) if total else 0,
        "par_type": [dict(r) for r in types],
        "par_mois": [dict(r) for r in par_mois],
    })


# ──────────────────────────────────────────────
# API — EXPORT CSV
# ──────────────────────────────────────────────
@app.route("/api/export/csv", methods=["GET"])
def export_csv():
    db = get_db()
    rows = db.execute("SELECT * FROM demandes ORDER BY created_at DESC").fetchall()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID","Prénom","Nom","Email","Téléphone","Montant","Durée","Type","Revenus","Situation","Statut","Note","Créé le","Mis à jour le"])
    for r in rows:
        writer.writerow([r["id"], r["prenom"], r["nom"], r["email"], r["telephone"] or "",
                         r["montant"], r["duree"], r["type_pret"], r["revenus"] or "",
                         r["situation"] or "", r["statut"], r["note"] or "",
                         r["created_at"], r["updated_at"]])
    output.seek(0)
    return send_file(
        io.BytesIO(("\ufeff" + output.getvalue()).encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"flexipret_export_{datetime.now().strftime('%Y%m%d')}.csv",
    )


# ──────────────────────────────────────────────
# API — UTILISATEURS
# ──────────────────────────────────────────────
@app.route("/api/utilisateurs", methods=["GET"])
def get_utilisateurs():
    db = get_db()
    rows = db.execute("SELECT * FROM utilisateurs ORDER BY created_at DESC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/utilisateurs", methods=["POST"])
def create_utilisateur():
    data = request.get_json(force=True)
    if not data.get("nom") or not data.get("email"):
        return jsonify({"error": "nom et email requis"}), 400
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO utilisateurs (nom, email, role) VALUES (?,?,?)",
            (data["nom"], data["email"], data.get("role", "conseiller")),
        )
        db.commit()
        new = db.execute("SELECT * FROM utilisateurs WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(dict(new)), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email déjà utilisé"}), 409


# ──────────────────────────────────────────────
# API — HISTORIQUE
# ──────────────────────────────────────────────
@app.route("/api/historique", methods=["GET"])
def get_historique():
    db = get_db()
    rows = db.execute(
        """SELECT h.*, d.prenom, d.nom FROM historique h
           LEFT JOIN demandes d ON d.id = h.demande_id
           ORDER BY h.created_at DESC LIMIT 100"""
    ).fetchall()
    return jsonify([dict(r) for r in rows])


# ──────────────────────────────────────────────
# API DOC
# ──────────────────────────────────────────────
@app.route("/api", methods=["GET"])
def api_index():
    return jsonify({
        "service": "FlexiPrêt API",
        "version": "1.0",
        "status": "online",
        "endpoints": {
            "GET    /api/demandes":            "Lister les demandes (?statut=...)",
            "POST   /api/demandes":            "Créer une demande",
            "GET    /api/demandes/:id":        "Détail + historique",
            "PUT    /api/demandes/:id/statut": "Changer le statut",
            "DELETE /api/demandes/:id":        "Supprimer",
            "GET    /api/stats":               "Statistiques",
            "GET    /api/export/csv":          "Export CSV",
            "GET    /api/utilisateurs":        "Conseillers",
            "POST   /api/utilisateurs":        "Créer un conseiller",
            "GET    /api/historique":          "Journal des actions",
        }
    })


# ──────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 FlexiPrêt sur http://localhost:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
else:
    # Appelé par gunicorn
    init_db()
