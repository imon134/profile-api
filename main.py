import httpx
import json
import sqlite3
import urllib.parse
import time
import random
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

DB_PATH = "/tmp/profiles.db"

# --- DB INIT ---
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS profiles (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE,
    gender TEXT,
    gender_probability REAL,
    sample_size INTEGER,
    age INTEGER,
    age_group TEXT,
    country_id TEXT,
    country_probability REAL,
    created_at TEXT
)
""")
conn.commit()

# --- HELPERS ---
def uuid_v7():
    return f"{int(time.time()*1000):x}-{random.getrandbits(48):x}"

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def age_group(age):
    if age <= 12:
        return "child"
    elif age <= 19:
        return "teenager"
    elif age <= 59:
        return "adult"
    return "senior"


# --- RESPONSE HELPER ---
def send(handler, code, payload):
    handler.send_response(code)
    handler.send_header("Content-type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(bytes(json.dumps(payload), "utf8"))


# --- HANDLER ---
class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path != "/main":
            return send(self, 404, {"status": "error", "message": "Route not found"})

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body or "{}")
        except:
            return send(self, 422, {"status": "error", "message": "Invalid JSON"})

        name = data.get("name")

        if not isinstance(name, str) or not name.strip():
            return send(self, 422, {"status": "error", "message": "Invalid name"})

        name = name.strip().lower()

        # check existing
        cursor.execute("SELECT * FROM profiles WHERE name=?", (name,))
        existing = cursor.fetchone()

        if existing:
            return send(self, 200, {
                "status": "success",
                "message": "Profile already exists",
                "data": {
                    "id": existing[0],
                    "name": existing[1],
                    "gender": existing[2],
                    "age": existing[5]
                }
            })

        # external APIs
        try:
            g = httpx.get("https://api.genderize.io", params={"name": name}).json()
            a = httpx.get("https://api.agify.io", params={"name": name}).json()
            n = httpx.get("https://api.nationalize.io", params={"name": name}).json()
        except:
            return send(self, 502, {"status": "error", "message": "External API failure"})

        countries = n.get("country", [])
        if not countries:
            return send(self, 502, {"status": "error", "message": "No nationality data"})

        top = max(countries, key=lambda x: x["probability"])

        pid = uuid_v7()
        created = now_iso()

        cursor.execute("""
        INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid,
            name,
            g.get("gender"),
            g.get("probability"),
            g.get("count"),
            a.get("age"),
            age_group(a.get("age") or 0),
            top["country_id"],
            top["probability"],
            created
        ))
        conn.commit()

        return send(self, 201, {
            "status": "success",
            "data": {
                "id": pid,
                "name": name,
                "gender": g.get("gender"),
                "age": a.get("age"),
                "country_id": top["country_id"],
                "created_at": created
            }
        })


    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # ---------------- GET ALL ----------------
        if path == "/main":
            cursor.execute("SELECT * FROM profiles")
            rows = cursor.fetchall()

            return send(self, 200, {
                "status": "success",
                "count": len(rows),
                "data": [
                    {
                        "id": r[0],
                        "name": r[1],
                        "gender": r[2],
                        "age": r[5],
                        "country_id": r[7]
                    } for r in rows
                ]
            })

        # ---------------- GET BY ID ----------------
        if path.startswith("/main/"):
            pid = path.split("/")[-1]

            cursor.execute("SELECT * FROM profiles WHERE id=?", (pid,))
            row = cursor.fetchone()

            if not row:
                return send(self, 404, {"status": "error", "message": "Profile not found"})

            return send(self, 200, {
                "status": "success",
                "data": {
                    "id": row[0],
                    "name": row[1],
                    "gender": row[2],
                    "age": row[5],
                    "country_id": row[7],
                    "created_at": row[9]
                }
            })

        return send(self, 404, {"status": "error", "message": "Route not found"})


    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/main/"):
            pid = path.split("/")[-1]

            cursor.execute("SELECT * FROM profiles WHERE id=?", (pid,))
            if not cursor.fetchone():
                return send(self, 404, {"status": "error", "message": "Profile not found"})

            cursor.execute("DELETE FROM profiles WHERE id=?", (pid,))
            conn.commit()

            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            return

        return send(self, 404, {"status": "error", "message": "Route not found"})