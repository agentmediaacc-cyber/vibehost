import os
import uuid
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename

load_dotenv(dotenv_path=Path(".env"))

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
app.config["UPLOAD_FOLDER"] = "static/uploads"
Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

def db():
    return psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        business_name = request.form.get("business_name")
        owner_name = request.form.get("owner_name")
        category = request.form.get("category")
        region = request.form.get("region")
        town = request.form.get("town")
        phone = request.form.get("phone")
        whatsapp = request.form.get("whatsapp")
        email = request.form.get("email")
        template_name = request.form.get("template_name", "modern")
        primary_color = request.form.get("primary_color", "#111827")

        logo_url = None
        logo = request.files.get("logo")
        if logo and logo.filename:
            filename = f"{uuid.uuid4()}_{secure_filename(logo.filename)}"
            logo.save(Path(app.config["UPLOAD_FOLDER"]) / filename)
            logo_url = f"/static/uploads/{filename}"

        conn = db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO business_profiles
            (business_name, owner_name, category, phone, whatsapp, email, logo_url)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (business_name, owner_name, category, phone, whatsapp, email, logo_url))

        business_id = cur.fetchone()["id"]

        cur.execute("""
            INSERT INTO business_sites
            (business_id, site_title, template_name, primary_color, hero_title, hero_subtitle, published)
            VALUES (%s,%s,%s,%s,%s,%s,false)
        """, (
            business_id,
            business_name,
            template_name,
            primary_color,
            f"Welcome to {business_name}",
            f"Professional services in {town}, {region}"
        ))

        cur.execute("""
            INSERT INTO subscriptions
            (business_id, plan_name, status)
            VALUES (%s,%s,%s)
        """, (business_id, "free_trial", "trial"))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("dashboard", business_id=business_id))

    return render_template("register.html")

@app.route("/dashboard/<business_id>")
def dashboard(business_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_profiles WHERE id=%s", (business_id,))
    business = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("dashboard.html", business=business)



@app.route("/site/<business_id>")
def public_site_preview(business_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_profiles WHERE id=%s", (business_id,))
    business = cur.fetchone()
    cur.execute("SELECT * FROM business_sites WHERE business_id=%s LIMIT 1", (business_id,))
    site = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("site_preview.html", business=business, site=site)

@app.route("/dashboard/<business_id>/upgrade")
def upgrade_business(business_id):
    return render_template("upgrade.html", business_id=business_id)

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/preview")
@app.route("/packages")
@app.route("/templates")
@app.route("/support")
def simple_pages():
    return render_template("home.html")

@app.route("/healthz")
def healthz():
    return {
        "status": "ok",
        "app": os.getenv("APP_NAME", "VibeHost"),
        "domain": os.getenv("APP_DOMAIN", "vibehost.namvibe.com")
    }

@app.route("/favicon.ico")
def favicon():
    return "", 204

if __name__ == "__main__":
    app.run(debug=True, port=5055)
