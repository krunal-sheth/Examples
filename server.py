#!/usr/bin/env python3
"""Dependency-free web server for the Jyotish application."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", ROOT / "data" / "jyotish.db"))
SESSION_DAYS = 30

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS birth_profiles (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  birth_date TEXT NOT NULL, birth_time TEXT NOT NULL, birthplace TEXT NOT NULL,
  latitude REAL NOT NULL, longitude REAL NOT NULL, timezone_offset REAL NOT NULL,
  kundli_json TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS predictions (
  id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  profile_id INTEGER NOT NULL REFERENCES birth_profiles(id), prediction_date TEXT NOT NULL,
  content_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(user_id, prediction_date)
);
CREATE TABLE IF NOT EXISTS feedback (
  prediction_id INTEGER PRIMARY KEY REFERENCES predictions(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  rating INTEGER NOT NULL CHECK(rating BETWEEN -1 AND 1), updated_at TEXT NOT NULL
);
"""

PLANETS = {
    "Sun": (280.46, 0.985647), "Moon": (218.32, 13.176396),
    "Mars": (355.43, 0.524039), "Mercury": (252.25, 4.092334),
    "Jupiter": (34.35, 0.083086), "Venus": (181.98, 1.602130),
    "Saturn": (50.08, 0.033459), "Rahu": (125.04, -0.052954),
}
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
NAKSHATRAS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
DASHA_LORDS = [("Ketu", 7), ("Venus", 20), ("Sun", 6), ("Moon", 10), ("Mars", 7), ("Rahu", 18), ("Jupiter", 16), ("Saturn", 19), ("Mercury", 17)]


def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def init_db():
    with db() as connection:
        connection.executescript(SCHEMA)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 310_000)
    return f"pbkdf2_sha256$310000${salt}${digest.hex()}"


def verify_password(password, encoded):
    try:
        _, _, salt, _ = encoded.split("$")
        return hmac.compare_digest(password_hash(password, salt), encoded)
    except ValueError:
        return False


def calculate_kundli(birth_date, birth_time, latitude, longitude, tz_offset):
    local_dt = datetime.fromisoformat(f"{birth_date}T{birth_time}")
    utc_dt = local_dt - timedelta(hours=float(tz_offset))
    epoch = datetime(2000, 1, 1, 12)
    days = (utc_dt - epoch).total_seconds() / 86400
    years_since_2000 = days / 365.2425
    ayanamsha = 23.85675 + years_since_2000 * 0.013968
    positions = {}
    for name, (origin, motion) in PLANETS.items():
        tropical = (origin + motion * days) % 360
        sidereal = (tropical - ayanamsha) % 360
        positions[name] = {"longitude": round(sidereal, 2), "sign": SIGNS[int(sidereal // 30)], "degree": round(sidereal % 30, 2)}
    positions["Ketu"] = {"longitude": round((positions["Rahu"]["longitude"] + 180) % 360, 2)}
    positions["Ketu"].update({"sign": SIGNS[int(positions["Ketu"]["longitude"] // 30)], "degree": round(positions["Ketu"]["longitude"] % 30, 2)})
    # Approximate local sidereal time provides a deterministic whole-sign ascendant.
    jd = days + 2451545.0
    lst = (280.46061837 + 360.98564736629 * (jd - 2451545.0) + float(longitude)) % 360
    ob = math.radians(23.4393)
    lat = math.radians(float(latitude))
    theta = math.radians(lst)
    asc = math.degrees(math.atan2(-math.cos(theta), math.sin(theta) * math.cos(ob) + math.tan(lat) * math.sin(ob))) % 360
    asc = (asc - ayanamsha) % 360
    moon = positions["Moon"]["longitude"]
    nak_index = int(moon / (360 / 27))
    pada = int((moon % (360 / 27)) / (360 / 108)) + 1
    lord, lord_years = DASHA_LORDS[nak_index % 9]
    elapsed_fraction = (moon % (360 / 27)) / (360 / 27)
    dasha_end = local_dt.date() + timedelta(days=(1 - elapsed_fraction) * lord_years * 365.2425)
    return {
        "ayanamsha": "Lahiri (approximate)", "ayanamsha_degrees": round(ayanamsha, 4),
        "ascendant": {"longitude": round(asc, 2), "sign": SIGNS[int(asc // 30)], "degree": round(asc % 30, 2)},
        "moon_sign": positions["Moon"]["sign"], "nakshatra": NAKSHATRAS[nak_index], "pada": pada,
        "current_dasha": lord, "first_dasha_end": dasha_end.isoformat(), "planets": positions,
        "calculation_version": "vedic-lite-1.0",
    }


def daily_prediction(kundli, target_date):
    seed = int(hashlib.sha256(f"{kundli['ascendant']['longitude']}:{target_date}".encode()).hexdigest()[:8], 16)
    themes = [
        ("Clarity through patience", "Let the shape of the situation reveal itself before you act. A measured response carries more influence today."),
        ("Honest connection", "A sincere conversation can soften an old tension. Listen for the feeling beneath the words."),
        ("Purposeful momentum", "Steady effort is more valuable than a dramatic beginning. Complete one meaningful task before adding another."),
        ("Return to balance", "Your energy improves when you protect the space between obligations. Choose rhythm over intensity."),
        ("A wider perspective", "What first appears to be a delay may be useful redirection. Stay open to an answer arriving differently."),
    ]
    title, summary = themes[seed % len(themes)]
    moon_house = ((date.fromisoformat(target_date).toordinal() + 4) % 12) + 1
    score = 62 + seed % 27
    categories = {
        "Relationships": themes[(seed + 1) % len(themes)][1],
        "Work & purpose": themes[(seed + 2) % len(themes)][1],
        "Wellbeing": themes[(seed + 3) % len(themes)][1],
    }
    return {"title": title, "summary": summary, "score": score, "energy": "Favorable" if score >= 72 else "Steady", "transit": f"Moon transiting your {moon_house}th house", "categories": categories, "reflection": "What becomes possible when you respond with intention rather than urgency?"}


class App(SimpleHTTPRequestHandler):
    server_version = "Jyotish/1.0"

    def log_message(self, fmt, *args):
        if os.getenv("QUIET") != "1":
            super().log_message(fmt, *args)

    def json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def send_json(self, data, status=200, headers=None):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items(): self.send_header(key, value)
        self.end_headers(); self.wfile.write(payload)

    def current_user(self, connection):
        jar = cookies.SimpleCookie(self.headers.get("Cookie")); morsel = jar.get("session")
        if not morsel: return None
        token_hash = hashlib.sha256(morsel.value.encode()).hexdigest()
        return connection.execute("SELECT users.* FROM sessions JOIN users ON users.id=sessions.user_id WHERE token_hash=? AND expires_at>?", (token_hash, now_iso())).fetchone()

    def require_user(self, connection):
        user = self.current_user(connection)
        if not user: self.send_json({"error": "Authentication required"}, 401)
        return user

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            return self.api_get(path)
        public_files = {"/", "/index.html", "/styles.css", "/example.js"}
        if path not in public_files:
            return self.send_error(404)
        if path == "/": self.path = "/index.html"
        return super().do_GET()

    def do_HEAD(self):
        path = urlparse(self.path).path
        if path not in {"/", "/index.html", "/styles.css", "/example.js"}:
            return self.send_error(404)
        if path == "/": self.path = "/index.html"
        return super().do_HEAD()

    def end_headers(self):
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        super().end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        try: body = self.json_body()
        except (json.JSONDecodeError, ValueError): return self.send_json({"error": "Invalid JSON"}, 400)
        try: return self.api_post(path, body)
        except (KeyError, TypeError, ValueError) as exc: return self.send_json({"error": str(exc) or "Invalid input"}, 400)

    def api_get(self, path):
        with db() as connection:
            user = self.require_user(connection)
            if not user: return
            if path == "/api/me":
                profile = connection.execute("SELECT * FROM birth_profiles WHERE user_id=? AND active=1 ORDER BY version DESC LIMIT 1", (user["id"],)).fetchone()
                return self.send_json({"user": {"id": user["id"], "name": user["name"], "email": user["email"]}, "profile": self.profile_json(profile) if profile else None})
            if path == "/api/history":
                rows = connection.execute("SELECT p.id,p.prediction_date,p.content_json,f.rating FROM predictions p LEFT JOIN feedback f ON f.prediction_id=p.id WHERE p.user_id=? ORDER BY p.prediction_date DESC LIMIT 60", (user["id"],)).fetchall()
                return self.send_json({"readings": [{"id": r["id"], "date": r["prediction_date"], "content": json.loads(r["content_json"]), "rating": r["rating"]} for r in rows]})
            if path.startswith("/api/prediction/"):
                target = path.rsplit("/", 1)[-1]; date.fromisoformat(target)
                profile = connection.execute("SELECT * FROM birth_profiles WHERE user_id=? AND active=1 ORDER BY version DESC LIMIT 1", (user["id"],)).fetchone()
                if not profile: return self.send_json({"error": "Complete your birth profile first"}, 409)
                row = connection.execute("SELECT * FROM predictions WHERE user_id=? AND prediction_date=?", (user["id"], target)).fetchone()
                if not row:
                    content = daily_prediction(json.loads(profile["kundli_json"]), target)
                    cursor = connection.execute("INSERT INTO predictions(user_id,profile_id,prediction_date,content_json,created_at) VALUES(?,?,?,?,?)", (user["id"], profile["id"], target, json.dumps(content), now_iso()))
                    connection.commit(); prediction_id = cursor.lastrowid
                else: content = json.loads(row["content_json"]); prediction_id = row["id"]
                feedback = connection.execute("SELECT rating FROM feedback WHERE prediction_id=?", (prediction_id,)).fetchone()
                return self.send_json({"id": prediction_id, "date": target, "content": content, "rating": feedback["rating"] if feedback else None})
            return self.send_json({"error": "Not found"}, 404)

    def profile_json(self, row):
        return {"id": row["id"], "birthDate": row["birth_date"], "birthTime": row["birth_time"], "birthplace": row["birthplace"], "latitude": row["latitude"], "longitude": row["longitude"], "timezoneOffset": row["timezone_offset"], "kundli": json.loads(row["kundli_json"]), "version": row["version"]}

    def api_post(self, path, body):
        with db() as connection:
            if path == "/api/register":
                name, email, password = body["name"].strip(), body["email"].strip().lower(), body["password"]
                if len(name) < 2 or "@" not in email or len(password) < 8: raise ValueError("Enter a name, valid email, and password of at least 8 characters")
                try: cursor = connection.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)", (name, email, password_hash(password), now_iso()))
                except sqlite3.IntegrityError: return self.send_json({"error": "An account with this email already exists"}, 409)
                return self.create_session(connection, cursor.lastrowid)
            if path == "/api/login":
                user = connection.execute("SELECT * FROM users WHERE email=?", (body["email"].strip().lower(),)).fetchone()
                if not user or not verify_password(body["password"], user["password_hash"]): return self.send_json({"error": "Incorrect email or password"}, 401)
                return self.create_session(connection, user["id"])
            user = self.require_user(connection)
            if not user: return
            if path == "/api/logout":
                jar = cookies.SimpleCookie(self.headers.get("Cookie")); morsel = jar.get("session")
                if morsel: connection.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(morsel.value.encode()).hexdigest(),)); connection.commit()
                return self.send_json({"ok": True}, headers={"Set-Cookie": "session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"})
            if path == "/api/profile":
                birth_date, birth_time, birthplace = body["birthDate"], body["birthTime"], body["birthplace"].strip()
                date.fromisoformat(birth_date); datetime.strptime(birth_time, "%H:%M")
                lat, lon, tz = float(body["latitude"]), float(body["longitude"]), float(body["timezoneOffset"])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180 and -14 <= tz <= 14): raise ValueError("Invalid location coordinates or timezone")
                kundli = calculate_kundli(birth_date, birth_time, lat, lon, tz)
                old = connection.execute("SELECT COALESCE(MAX(version),0) version FROM birth_profiles WHERE user_id=?", (user["id"],)).fetchone()
                connection.execute("UPDATE birth_profiles SET active=0 WHERE user_id=?", (user["id"],))
                cursor = connection.execute("INSERT INTO birth_profiles(user_id,birth_date,birth_time,birthplace,latitude,longitude,timezone_offset,kundli_json,version,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (user["id"], birth_date, birth_time, birthplace, lat, lon, tz, json.dumps(kundli), old["version"] + 1, now_iso()))
                connection.commit(); row = connection.execute("SELECT * FROM birth_profiles WHERE id=?", (cursor.lastrowid,)).fetchone()
                return self.send_json({"profile": self.profile_json(row)}, 201)
            if path.startswith("/api/feedback/"):
                prediction_id, rating = int(path.rsplit("/", 1)[-1]), int(body["rating"])
                if rating not in (-1, 0, 1): raise ValueError("Rating must be -1, 0, or 1")
                owned = connection.execute("SELECT 1 FROM predictions WHERE id=? AND user_id=?", (prediction_id, user["id"])).fetchone()
                if not owned: return self.send_json({"error": "Prediction not found"}, 404)
                connection.execute("INSERT INTO feedback(prediction_id,user_id,rating,updated_at) VALUES(?,?,?,?) ON CONFLICT(prediction_id) DO UPDATE SET rating=excluded.rating,updated_at=excluded.updated_at", (prediction_id, user["id"], rating, now_iso()))
                connection.commit(); return self.send_json({"ok": True})
            return self.send_json({"error": "Not found"}, 404)

    def create_session(self, connection, user_id):
        token = secrets.token_urlsafe(32); expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
        connection.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), user_id, expires.isoformat())); connection.commit()
        return self.send_json({"ok": True}, 201, {"Set-Cookie": f"session={token}; Path=/; Max-Age={SESSION_DAYS * 86400}; HttpOnly; SameSite=Lax"})


def run():
    init_db(); port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), App)
    print(f"Jyotish listening on http://0.0.0.0:{port}"); server.serve_forever()


if __name__ == "__main__": run()
