from flask import Flask, jsonify, Response
from flask_cors import CORS

import sys
import os
import json
from db import save_norm, init_db, get_or_create_law  

from db import save_norm, init_db, get_or_create_law  

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'law_scraper')))
from db import init_db

app = Flask(__name__)
CORS(app)

conn = init_db

@app.route("/api/laws")
def get_laws():
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM laws ORDER BY name ASC")
    rows = cursor.fetchall()
    laws = [{"id": row[0], "name": row[1]} for row in rows]
    return jsonify(laws)

@app.route("/api/laws/<int:law_id>/norms")
def get_norms_by_law(law_id):
    # returns all norms for the given law
    return jsonify(fetch_norms_by_law(law_id))

@app.route("/api/norms/<int:norm_id>")
def get_norm(norm_id):
    # returns full norm data (number, title, content)
    return jsonify(fetch_norm_by_id(norm_id))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)