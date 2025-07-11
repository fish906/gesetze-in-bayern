from flask import Flask, jsonify
from flask_cors import CORS
import pymysql

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'law_scraper')))
from db import init_db

app = Flask(__name__)
CORS(app)

from flask import Response
import json

@app.route("/api/article-one")
def article_one():
    conn = init_db()
    try:
        with conn.cursor() as c:
            c.execute("""
                SELECT n.number, n.title, n.content
                FROM norms n
                JOIN laws l ON n.law_id = l.id
                WHERE l.name = %s AND n.number= %s
                LIMIT 1
            """, ('BayGO', 'Art. 6'))
            row = c.fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404

        payload = {
            "number": row[0],
            "title": row[1],
            "content": row[2]
        }
        return Response(json.dumps(payload), mimetype='application/json')
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)