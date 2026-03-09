#!/usr/bin/env python3
"""Calories tracker API server — bridges SQLite DB to the web app."""
import json
import sqlite3
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = os.path.join(os.path.dirname(__file__), "calories.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def json_response(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", len(body))
    handler.end_headers()
    handler.wfile.write(body)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(__file__), **kwargs)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/api/meal":
            self.handle_add_meal(body)
        elif path == "/api/meal/item":
            self.handle_add_item(body)
        elif path == "/api/weight":
            self.handle_add_weight(body)
        elif path == "/api/profile":
            self.handle_update_profile(body)
        elif path == "/api/steps":
            self.handle_add_steps(body)
        elif path == "/api/health":
            self.handle_health(body)
        elif path == "/api/dish":
            self.handle_add_dish(body)
        elif path == "/api/dish/photo":
            self.handle_upload_dish_photo()
        elif path == "/api/meal/from-dish":
            self.handle_meal_from_dish(body)
        else:
            json_response(self, {"error": "not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/meal":
            meal_id = int(qs.get("id", [0])[0])
            self.handle_delete_meal(meal_id)
        elif path == "/api/meal/item":
            item_id = int(qs.get("id", [0])[0])
            self.handle_delete_item(item_id)
        elif path == "/api/dish":
            dish_id = int(qs.get("id", [0])[0])
            self.handle_delete_dish(dish_id)
        else:
            json_response(self, {"error": "not found"}, 404)

    def handle_add_meal(self, body):
        """POST /api/meal {date?, meal_type, note?, items: [{name, kcal, protein, carbs, fat, quantity?}]}"""
        from datetime import datetime, timezone, timedelta
        paris = timezone(timedelta(hours=1))
        date = body.get("date", datetime.now(paris).strftime("%Y-%m-%d"))
        meal_type = body.get("meal_type", "snack")
        note = body.get("note")
        items = body.get("items", [])

        db = get_db()
        cur = db.execute("INSERT INTO meals (date, meal_type, note) VALUES (?, ?, ?)",
                         (date, meal_type, note))
        meal_id = cur.lastrowid
        for it in items:
            db.execute("""INSERT INTO food_items (meal_id, name, kcal, protein, carbs, fat, quantity)
                          VALUES (?, ?, ?, ?, ?, ?, ?)""",
                       (meal_id, it["name"], it.get("kcal", 0), it.get("protein", 0),
                        it.get("carbs", 0), it.get("fat", 0), it.get("quantity", "1")))
        self._update_daily_totals(db, date)
        db.commit()
        db.close()
        json_response(self, {"ok": True, "meal_id": meal_id}, 201)

    def handle_add_item(self, body):
        """POST /api/meal/item {meal_id, name, kcal, protein, carbs, fat, quantity?}"""
        db = get_db()
        meal = db.execute("SELECT date FROM meals WHERE id=?", (body["meal_id"],)).fetchone()
        if not meal:
            db.close()
            return json_response(self, {"error": "meal not found"}, 404)
        db.execute("""INSERT INTO food_items (meal_id, name, kcal, protein, carbs, fat, quantity)
                      VALUES (?, ?, ?, ?, ?, ?, ?)""",
                   (body["meal_id"], body["name"], body.get("kcal", 0), body.get("protein", 0),
                    body.get("carbs", 0), body.get("fat", 0), body.get("quantity", "1")))
        self._update_daily_totals(db, meal["date"])
        db.commit()
        db.close()
        json_response(self, {"ok": True}, 201)

    def handle_delete_meal(self, meal_id):
        db = get_db()
        meal = db.execute("SELECT date FROM meals WHERE id=?", (meal_id,)).fetchone()
        if not meal:
            db.close()
            return json_response(self, {"error": "not found"}, 404)
        db.execute("DELETE FROM food_items WHERE meal_id=?", (meal_id,))
        db.execute("DELETE FROM meals WHERE id=?", (meal_id,))
        self._update_daily_totals(db, meal["date"])
        db.commit()
        db.close()
        json_response(self, {"ok": True})

    def handle_delete_item(self, item_id):
        db = get_db()
        row = db.execute("SELECT m.date FROM food_items f JOIN meals m ON m.id=f.meal_id WHERE f.id=?", (item_id,)).fetchone()
        if not row:
            db.close()
            return json_response(self, {"error": "not found"}, 404)
        db.execute("DELETE FROM food_items WHERE id=?", (item_id,))
        self._update_daily_totals(db, row["date"])
        db.commit()
        db.close()
        json_response(self, {"ok": True})

    def handle_add_weight(self, body):
        """POST /api/weight {date?, weight_kg}"""
        from datetime import datetime, timezone, timedelta
        paris = timezone(timedelta(hours=1))
        date = body.get("date", datetime.now(paris).strftime("%Y-%m-%d"))
        db = get_db()
        db.execute("INSERT OR REPLACE INTO weight_log (date, weight_kg) VALUES (?, ?)",
                   (date, body["weight_kg"]))
        db.commit()
        db.close()
        json_response(self, {"ok": True}, 201)

    def handle_update_profile(self, body):
        """POST /api/profile {target_kcal?, protein_ratio?, carbs_ratio?, fat_ratio?, weight_kg?, ...}"""
        db = get_db()
        allowed = ["weight_kg", "height_cm", "age", "activity", "activity_multiplier",
                    "bmr", "tdee", "deficit", "target_kcal", "protein_ratio", "carbs_ratio",
                    "fat_ratio", "goal"]
        sets = []
        vals = []
        for k in allowed:
            if k in body:
                sets.append(f"{k}=?")
                vals.append(body[k])
        if sets:
            vals.append(1)
            db.execute(f"UPDATE profile SET {', '.join(sets)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", vals)
            db.commit()
        row = db.execute("SELECT * FROM profile WHERE id=1").fetchone()
        db.close()
        json_response(self, dict(row))

    def handle_add_steps(self, body):
        """POST /api/steps {date?, steps}"""
        from datetime import datetime, timezone, timedelta
        paris = timezone(timedelta(hours=1))
        date = body.get("date", datetime.now(paris).strftime("%Y-%m-%d"))
        db = get_db()
        db.execute("INSERT OR REPLACE INTO steps_log (date, steps) VALUES (?, ?)",
                   (date, body["steps"]))
        db.commit()
        db.close()
        json_response(self, {"ok": True}, 201)

    def handle_health(self, body):
        """POST /api/health {date?, steps?, weight_kg?} — combo endpoint for iOS Shortcuts"""
        from datetime import datetime, timezone, timedelta
        paris = timezone(timedelta(hours=1))
        date = body.get("date", datetime.now(paris).strftime("%Y-%m-%d"))
        db = get_db()
        logged = {}
        if "steps" in body:
            db.execute("INSERT OR REPLACE INTO steps_log (date, steps) VALUES (?, ?)",
                       (date, body["steps"]))
            logged["steps"] = body["steps"]
        if "weight_kg" in body:
            db.execute("INSERT OR REPLACE INTO weight_log (date, weight_kg) VALUES (?, ?)",
                       (date, body["weight_kg"]))
            logged["weight_kg"] = body["weight_kg"]
        db.commit()
        db.close()
        json_response(self, {"ok": True, "date": date, "logged": logged}, 201)

    def handle_add_dish(self, body):
        """POST /api/dish {name, description?, kcal, protein, carbs, fat, default_quantity?, photo?}"""
        db = get_db()
        cur = db.execute("""INSERT INTO dishes (name, description, kcal, protein, carbs, fat, default_quantity, photo)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                         (body["name"], body.get("description"), body.get("kcal", 0),
                          body.get("protein", 0), body.get("carbs", 0), body.get("fat", 0),
                          body.get("default_quantity", "1 portion"), body.get("photo")))
        db.commit()
        dish_id = cur.lastrowid
        db.close()
        json_response(self, {"ok": True, "dish_id": dish_id}, 201)

    def handle_upload_dish_photo(self):
        """POST /api/dish/photo — multipart upload, returns filename"""
        import cgi
        import uuid
        photos_dir = os.path.join(os.path.dirname(__file__), "photos")
        os.makedirs(photos_dir, exist_ok=True)
        content_type = self.headers.get("Content-Type", "")
        if "multipart" in content_type:
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers,
                                     environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type})
            file_item = form["file"]
            ext = os.path.splitext(file_item.filename)[1] if file_item.filename else ".jpg"
            fname = f"{uuid.uuid4().hex}{ext}"
            with open(os.path.join(photos_dir, fname), "wb") as f:
                f.write(file_item.file.read())
        else:
            length = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(length)
            ext = ".jpg"
            ct = self.headers.get("Content-Type", "")
            if "png" in ct: ext = ".png"
            elif "webp" in ct: ext = ".webp"
            fname = f"{uuid.uuid4().hex}{ext}"
            with open(os.path.join(photos_dir, fname), "wb") as f:
                f.write(data)
        json_response(self, {"ok": True, "photo": fname}, 201)

    def handle_serve_photo(self, path):
        """GET /api/dish/photo/<filename>"""
        fname = path.split("/")[-1]
        photos_dir = os.path.join(os.path.dirname(__file__), "photos")
        fpath = os.path.join(photos_dir, fname)
        if not os.path.exists(fpath):
            return json_response(self, {"error": "not found"}, 404)
        ext = os.path.splitext(fname)[1].lower()
        ct = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
        with open(fpath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", len(data))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def handle_list_dishes(self):
        """GET /api/dishes"""
        db = get_db()
        rows = db.execute("SELECT * FROM dishes ORDER BY times_used DESC, name").fetchall()
        db.close()
        json_response(self, [dict(r) for r in rows])

    def handle_get_dish(self, dish_id):
        """GET /api/dish?id=X"""
        db = get_db()
        row = db.execute("SELECT * FROM dishes WHERE id=?", (dish_id,)).fetchone()
        db.close()
        if row:
            json_response(self, dict(row))
        else:
            json_response(self, {"error": "not found"}, 404)

    def handle_delete_dish(self, dish_id):
        """DELETE /api/dish?id=X"""
        db = get_db()
        db.execute("DELETE FROM dishes WHERE id=?", (dish_id,))
        db.commit()
        db.close()
        json_response(self, {"ok": True})

    def handle_meal_from_dish(self, body):
        """POST /api/meal/from-dish {dish_id, date?, meal_type, multiplier?}"""
        from datetime import datetime, timezone, timedelta
        paris = timezone(timedelta(hours=1))
        date = body.get("date", datetime.now(paris).strftime("%Y-%m-%d"))
        meal_type = body.get("meal_type", "snack")
        mult = body.get("multiplier", 1.0)

        db = get_db()
        dish = db.execute("SELECT * FROM dishes WHERE id=?", (body["dish_id"],)).fetchone()
        if not dish:
            db.close()
            return json_response(self, {"error": "dish not found"}, 404)

        cur = db.execute("INSERT INTO meals (date, meal_type, note) VALUES (?, ?, ?)",
                         (date, meal_type, f"🍽 {dish['name']}"))
        meal_id = cur.lastrowid
        db.execute("""INSERT INTO food_items (meal_id, name, kcal, protein, carbs, fat, quantity)
                      VALUES (?, ?, ?, ?, ?, ?, ?)""",
                   (meal_id, dish["name"], int(dish["kcal"] * mult),
                    round(dish["protein"] * mult, 1), round(dish["carbs"] * mult, 1),
                    round(dish["fat"] * mult, 1), dish["default_quantity"]))
        db.execute("UPDATE dishes SET times_used = times_used + 1, updated_at = datetime('now') WHERE id=?",
                   (body["dish_id"],))
        db.commit()
        db.close()
        json_response(self, {"ok": True, "meal_id": meal_id}, 201)

    def _update_daily_totals(self, db, date):
        pass  # daily_totals is a VIEW, auto-computed

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/api/profile":
            self.handle_profile()
        elif path == "/api/today" or path == "/api/day":
            date = qs.get("date", [None])[0]
            self.handle_day(date)
        elif path == "/api/history":
            days = int(qs.get("days", ["30"])[0])
            self.handle_history(days)
        elif path == "/api/weight":
            self.handle_weight_history()
        elif path == "/api/dishes":
            self.handle_list_dishes()
        elif path == "/api/dish":
            dish_id = int(qs.get("id", [0])[0])
            self.handle_get_dish(dish_id)
        elif path.startswith("/api/dish/photo/"):
            self.handle_serve_photo(path)
        elif path == "/":
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def handle_profile(self):
        db = get_db()
        row = db.execute("SELECT * FROM profile WHERE id=1").fetchone()
        db.close()
        if row:
            json_response(self, dict(row))
        else:
            json_response(self, {"error": "no profile"}, 404)

    def handle_day(self, date=None):
        db = get_db()
        if not date:
            from datetime import datetime, timezone, timedelta
            paris = timezone(timedelta(hours=1))
            date = datetime.now(paris).strftime("%Y-%m-%d")

        profile = db.execute("SELECT target_kcal, protein_ratio, carbs_ratio, fat_ratio FROM profile WHERE id=1").fetchone()
        target = dict(profile) if profile else {"target_kcal": 1613}

        meals = db.execute("""
            SELECT m.id, m.meal_type, m.note, m.created_at FROM meals m
            WHERE m.date = ? ORDER BY m.id
        """, (date,)).fetchall()

        result = {"date": date, "target": target, "meals": [], "totals": {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}}

        for meal in meals:
            items = db.execute("""
                SELECT name, kcal, protein, carbs, fat, quantity FROM food_items
                WHERE meal_id = ? ORDER BY id
            """, (meal["id"],)).fetchall()
            items_list = [dict(i) for i in items]
            meal_kcal = sum(i["kcal"] for i in items_list)
            meal_p = sum(i["protein"] or 0 for i in items_list)
            meal_g = sum(i["carbs"] or 0 for i in items_list)
            meal_l = sum(i["fat"] or 0 for i in items_list)

            result["meals"].append({
                "id": meal["id"],
                "type": meal["meal_type"],
                "note": meal["note"],
                "items": items_list,
                "totals": {"kcal": meal_kcal, "protein": meal_p, "carbs": meal_g, "fat": meal_l}
            })
            result["totals"]["kcal"] += meal_kcal
            result["totals"]["protein"] += meal_p
            result["totals"]["carbs"] += meal_g
            result["totals"]["fat"] += meal_l

        result["remaining"] = target["target_kcal"] - result["totals"]["kcal"]
        db.close()
        json_response(self, result)

    def handle_history(self, days=30):
        db = get_db()
        rows = db.execute("""
            SELECT d.*, w.weight_kg FROM daily_totals d
            LEFT JOIN weight_log w ON w.date = d.date
            ORDER BY d.date DESC LIMIT ?
        """, (days,)).fetchall()
        profile = db.execute("SELECT target_kcal FROM profile WHERE id=1").fetchone()
        target = profile["target_kcal"] if profile else 1613
        db.close()
        json_response(self, {
            "target": target,
            "days": [dict(r) for r in rows]
        })

    def handle_weight_history(self):
        db = get_db()
        rows = db.execute("SELECT date, weight_kg FROM weight_log ORDER BY date DESC LIMIT 90").fetchall()
        db.close()
        json_response(self, [dict(r) for r in rows])

    def log_message(self, format, *args):
        pass  # silent

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8888), Handler)
    print("Calories server running on http://0.0.0.0:8888")
    server.serve_forever()
