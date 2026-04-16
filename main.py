import httpx
import json
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
import time, random

DB_PATH = "/tmp/profiles.db"

# DB INIT
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



def uuid_v7():
    ts = int(time.time() * 1000)
    rand = random.getrandbits(48)
    return f"{ts:012x}-{rand:012x}"

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

def send_json(handler, code, payload):
    handler.send_response(code)
    handler.send_header("Content-type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(bytes(json.dumps(payload), "utf8"))

def error(handler, code, message):
    send_json(handler, code, {
        "status": "error",
        "message": message
    })

def fetch_external(name):
    try:
        g = httpx.get("https://api.genderize.io", params={"name": name}).json()
        a = httpx.get("https://api.agify.io", params={"name": name}).json()
        n = httpx.get("https://api.nationalize.io", params={"name": name}).json()
    except Exception:
        raise (502, "Upstream failure")

    if not g.get("gender") or g.get("count") == 0:
        raise (502, "Genderize returned an invalid response")

    if a.get("age") is None:
        raise (502, "Agify returned an invalid response")

    countries = n.get("country", [])
    if not countries:
        raise (502, "Nationalize returned an invalid response")

    top = max(countries, key=lambda x: x["probability"])

    return {
        "gender": g["gender"],
        "gender_probability": g["probability"],
        "sample_size": g["count"],
        "age": a["age"],
        "age_group": age_group(a["age"]),
        "country_id": top["country_id"],
        "country_probability": top["probability"]
    }

def row_to_dict(r):
    return {
        "id": r[0],
        "name": r[1],
        "gender": r[2],
        "gender_probability": r[3],
        "sample_size": r[4],
        "age": r[5],
        "age_group": r[6],
        "country_id": r[7],
        "country_probability": r[8],
        "created_at": r[9]
    }



class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        if self.path != "/main":
            return error(self, 404, "Profile not found")

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except:
            return error(self, 422, "Invalid type")

        name = data.get("name")

        if not isinstance(name, str):
            return error(self, 422, "Invalid type")

        name = name.strip().lower()

        if not name:
            return error(self, 400, "Missing or empty name")

        cursor.execute("SELECT * FROM profiles WHERE name=?", (name,))
        existing = cursor.fetchone()

        if existing:
            return send_json(self, 200, {
                "status": "success",
                "message": "Profile already exists",
                "data": row_to_dict(existing)
            })

        try:
            ext = fetch_external(name)
        except Exception as e:
            code, msg = e.args if len(e.args) == 2 else (502, "Upstream failure")
            return error(self, code, msg)

        pid = uuid_v7()
        created_at = now_iso()

        cursor.execute("""
        INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pid,
            name,
            ext["gender"],
            ext["gender_probability"],
            ext["sample_size"],
            ext["age"],
            ext["age_group"],
            ext["country_id"],
            ext["country_probability"],
            created_at
        ))
        conn.commit()

        return send_json(self, 201, {
            "status": "success",
            "data": {
                "id": pid,
                "name": name,
                **ext,
                "created_at": created_at
            }
        })

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path.startswith("/main"):
            pid = parsed.path.split("/")[-1]

            cursor.execute("SELECT * FROM profiles WHERE id=?", (pid,))
            row = cursor.fetchone()

            if not row:
                return error(self, 404, "Profile not found")

            return send_json(self, 200, {
                "status": "success",
                "data": row_to_dict(row)
            })

        if parsed.path == "/main":
            params = urllib.parse.parse_qs(parsed.query)

            gender = params.get("gender", [None])[0]
            country = params.get("country_id", [None])[0]
            age_g = params.get("age_group", [None])[0]

            query = "SELECT id, name, gender, age, age_group, country_id FROM profiles WHERE 1=1"
            values = []

            if gender:
                query += " AND LOWER(gender)=?"
                values.append(gender.lower())

            if country:
                query += " AND LOWER(country_id)=?"
                values.append(country.lower())

            if age_g:
                query += " AND LOWER(age_group)=?"
                values.append(age_g.lower())

            cursor.execute(query, values)
            rows = cursor.fetchall()

            data = [
                {
                    "id": r[0],
                    "name": r[1],
                    "gender": r[2],
                    "age": r[3],
                    "age_group": r[4],
                    "country_id": r[5]
                } for r in rows
            ]

            return send_json(self, 200, {
                "status": "success",
                "count": len(data),
                "data": data
            })

        return error(self, 404, "Profile not found")

    def do_DELETE(self):
        if not self.path.startswith("/main"):
            return error(self, 404, "Profile not found")

        pid = self.path.split("/")[-1]

        cursor.execute("SELECT * FROM profiles WHERE id=?", (pid,))
        if not cursor.fetchone():
            return error(self, 404, "Profile not found")

        cursor.execute("DELETE FROM profiles WHERE id=?", (pid,))
        conn.commit()

        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
