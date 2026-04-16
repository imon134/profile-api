import httpx
import json
import sqlite3
import time
import random
from datetime import datetime, timezone

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

def fetch_external(name):
    g = httpx.get("https://api.genderize.io", params={"name": name}).json()
    a = httpx.get("https://api.agify.io", params={"name": name}).json()
    n = httpx.get("https://api.nationalize.io", params={"name": name}).json()

    countries = n.get("country", [])
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

def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(body)
    }

# --- VERCEL ENTRYPOINT ---
def handler(request):

    method = request.get("method")
    path = request.get("path")

    # body parsing (Vercel sends raw string)
    try:
        body = request.get("body")
        data = json.loads(body) if body else {}
    except:
        data = {}

    # ---------------- CREATE PROFILE ----------------
    if method == "POST" and path == "/main":
        name = data.get("name")

        if not isinstance(name, str) or not name.strip():
            return response(422, {"status": "error", "message": "Invalid name"})

        name = name.strip().lower()

        cursor.execute("SELECT * FROM profiles WHERE name=?", (name,))
        existing = cursor.fetchone()

        if existing:
            return response(200, {
                "status": "success",
                "message": "Profile already exists",
                "data": row_to_dict(existing)
            })

        ext = fetch_external(name)

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

        return response(201, {
            "status": "success",
            "data": {
                "id": pid,
                "name": name,
                **ext,
                "created_at": created_at
            }
        })

    # ---------------- GET ALL ----------------
    if method == "GET" and path == "/main":
        cursor.execute("SELECT * FROM profiles")
        rows = cursor.fetchall()

        return response(200, {
            "status": "success",
            "count": len(rows),
            "data": [row_to_dict(r) for r in rows]
        })

    # ---------------- GET BY ID ----------------
    if method == "GET" and path.startswith("/main/"):
        pid = path.split("/")[-1]

        cursor.execute("SELECT * FROM profiles WHERE id=?", (pid,))
        row = cursor.fetchone()

        if not row:
            return response(404, {"status": "error", "message": "Profile not found"})

        return response(200, {
            "status": "success",
            "data": row_to_dict(row)
        })

    # ---------------- DELETE ----------------
    if method == "DELETE" and path.startswith("/main/"):
        pid = path.split("/")[-1]

        cursor.execute("SELECT * FROM profiles WHERE id=?", (pid,))
        if not cursor.fetchone():
            return response(404, {"status": "error", "message": "Profile not found"})

        cursor.execute("DELETE FROM profiles WHERE id=?", (pid,))
        conn.commit()

        return response(204, {})

    return response(404, {"status": "error", "message": "Route not found"})