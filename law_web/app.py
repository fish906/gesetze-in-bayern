import os
from flask import Flask, jsonify, render_template
from law_scraper.db import init_db

app = Flask(__name__, static_folder="index.html")
conn = init_db()

@app.route('/norms')
def get_norms():
    cursor = conn.cursor()
    cursor.execute("SELECT id, law_id, number, title, content FROM norms")
    rows = cursor.fetchall()
    norms = []
    for row in rows:
        norms.append({
            'id': row[0],
            'law_id': row[1],
            'number': row[2],
            'title': row[3],
            'content': row[4]
        })
    return jsonify(norms)

@app.route('/')
def serve_index():
    return render_template('index.html')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
