import logging
import os
import re
import uuid
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, url_for
from psycopg2.extras import RealDictCursor
from werkzeug.utils import secure_filename

try:
    from supabase import create_client
except Exception:
    create_client = None

load_dotenv(dotenv_path=Path(".env"))

BASE_DOMAIN = os.getenv("BASE_DOMAIN", "namvibe.com")
RESERVED_SUBDOMAINS = {"www", "namvibe", "vibehost", "admin", "api", "tarasi"}
UPLOAD_FOLDER = Path("static/uploads")
SUPPORT_PHONE = "+264812613261"
SUPPORT_WHATSAPP_URL = "https://wa.me/264812613261"

TEMPLATE_MAP = {
    "retail-shop": "website_templates/retail_shop.html",
    "restaurant-food": "website_templates/restaurant_food.html",
    "transport-shuttle": "website_templates/transport_shuttle.html",
    "guesthouse-lodge": "website_templates/guesthouse_lodge.html",
    "salon-beauty": "website_templates/salon_beauty.html",
    "beauty-salon": "website_templates/salon_beauty.html",
    "school-education": "website_templates/school_education.html",
    "health-wellness": "website_templates/health_wellness.html",
    "construction": "website_templates/construction_repair.html",
    "cleaning-services": "website_templates/cleaning_services.html",
}

TEMPLATE_ROWS = [
    {
        "name": "Retail Shop",
        "slug": "retail-shop",
        "category": "retail",
        "description": "Product catalog, featured deals, WhatsApp orders and a polished storefront.",
    },
    {
        "name": "Restaurant and Food",
        "slug": "restaurant-food",
        "category": "food",
        "description": "Menus, meal promotions, delivery flow and table or catering enquiries.",
    },
    {
        "name": "Transport and Shuttle",
        "slug": "transport-shuttle",
        "category": "transport",
        "description": "Airport transfers, route cards, booking requests and operator tools.",
    },
    {
        "name": "Guesthouse and Lodge",
        "slug": "guesthouse-lodge",
        "category": "hospitality",
        "description": "Room previews, stay enquiries, amenity highlights and booking prompts.",
    },
    {
        "name": "Salon and Beauty",
        "slug": "salon-beauty",
        "category": "beauty",
        "description": "Hair, nails, makeup and appointment-driven service presentation.",
    },
    {
        "name": "School and Education",
        "slug": "school-education",
        "category": "education",
        "description": "Admissions, parent communication, notices and academic feature blocks.",
    },
    {
        "name": "Health and Wellness",
        "slug": "health-wellness",
        "category": "health",
        "description": "Consultation enquiries, wellness services and clinic-style credibility.",
    },
    {
        "name": "Construction and Repair",
        "slug": "construction",
        "category": "construction",
        "description": "Project showcases, quotation flows and contractor-oriented service pages.",
    },
    {
        "name": "Cleaning Services",
        "slug": "cleaning-services",
        "category": "services",
        "description": "Recurring plans, quote requests, service packages and cleaning teams.",
    },
]

REGION_OPTIONS = [
    "Khomas",
    "Erongo",
    "Oshana",
    "Ohangwena",
    "Omusati",
    "Oshikoto",
    "Otjozondjupa",
    "Kunene",
    "Hardap",
    "Karas",
    "Kavango East",
    "Kavango West",
    "Zambezi",
    "Omaheke",
]

FONT_STYLE_MAP = {
    "modern": "Inter, Arial, sans-serif",
    "luxury": "Georgia, 'Times New Roman', serif",
    "friendly": "'Trebuchet MS', Verdana, sans-serif",
}


class AttrDict(dict):
    def __getattr__(self, key):
        return self.get(key)


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger(__name__)


def db():
    return psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)


def supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key or create_client is None:
        return None
    try:
        return create_client(url, key)
    except Exception as exc:
        logger.warning("Supabase client unavailable: %s", exc)
        return None


def slugify(value):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:40] or "site"


def unique_subdomain(cur, wanted):
    base = slugify(wanted)
    if base in RESERVED_SUBDOMAINS:
        base = f"{base}-site"

    candidate = base
    counter = 2
    while True:
        cur.execute("SELECT id FROM business_profiles WHERE subdomain=%s LIMIT 1", (candidate,))
        if not cur.fetchone():
            return candidate
        candidate = f"{base}{counter}"
        counter += 1


def current_subdomain():
    host = (request.host or "").split(":")[0].lower()
    if not host or host in {"127.0.0.1", "localhost"}:
        return None
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", host):
        return None
    if host == BASE_DOMAIN or not host.endswith(f".{BASE_DOMAIN}"):
        return None

    label = host[: -(len(BASE_DOMAIN) + 1)]
    if not label or "." in label or label in RESERVED_SUBDOMAINS:
        return None
    return label


def get_template_meta(slug):
    canonical_slug = "salon-beauty" if slug == "beauty-salon" else slug
    for row in TEMPLATE_ROWS:
        if row["slug"] == canonical_slug:
            return row
    return None


def list_templates():
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name, slug, category, description
            FROM website_templates
            WHERE active = true
            ORDER BY name
            """
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if rows:
            return rows
    except Exception:
        pass
    return TEMPLATE_ROWS


def supabase_table_exists(client, table_name):
    try:
        client.table(table_name).select("*").limit(1).execute()
        return True
    except Exception as exc:
        message = str(exc).lower()
        if "could not find the table" in message or "does not exist" in message:
            return False
        logger.warning("Supabase table check failed for %s: %s", table_name, exc)
        return False


def sync_site_metadata_to_supabase(business_id, business, site):
    client = supabase_client()
    if not client:
        return
    if not supabase_table_exists(client, "vibehost_sites"):
        return

    payload = {
        "business_id": str(business_id),
        "business_name": business["business_name"],
        "subdomain": business["subdomain"],
        "template_name": site["template_name"],
        "live_url": site["live_url"],
        "town": business.get("town"),
        "region": business.get("region"),
        "phone": business.get("phone"),
        "email": business.get("email"),
    }
    try:
        client.table("vibehost_sites").upsert(payload).execute()
    except Exception as exc:
        logger.warning("Supabase metadata sync failed for business %s: %s", business_id, exc)


def upload_logo(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    filename = f"{uuid.uuid4().hex}_{secure_filename(file_storage.filename)}"
    file_storage.save(UPLOAD_FOLDER / filename)
    return f"/static/uploads/{filename}"


def demo_context(slug):
    meta = get_template_meta(slug) or get_template_meta("retail-shop")
    business = AttrDict(
        {
            "business_name": "Kasera Demo Studio",
            "owner_name": "VibeHost Demo",
            "description": f"Preview the full {meta['name']} website with realistic layout and sample branding before creating your own live site.",
            "town": "Windhoek",
            "region": "Khomas",
            "email": "hello@demo.namvibe.com",
            "phone": "+264 81 000 0000",
            "whatsapp": "264810000000",
            "logo_url": None,
            "subdomain": "demo-site",
            "website_type": meta["slug"],
        }
    )
    site = AttrDict(
        {
            "site_title": business["business_name"],
            "template_name": meta["slug"],
            "primary_color": "#0f172a",
            "secondary_color": "#f59e0b",
            "accent_color": "#f97316",
            "hero_title": business["business_name"],
            "hero_subtitle": business["description"],
            "background_image": None,
            "background_image_url": None,
            "font_style": "modern",
            "font_family": FONT_STYLE_MAP["modern"],
            "wallpaper_style": "premium",
            "live_url": f"https://demo-site.{BASE_DOMAIN}",
            "published": True,
        }
    )
    return business, site


def fetch_business_site_by_subdomain(subdomain):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM business_profiles
        WHERE subdomain=%s
        LIMIT 1
        """,
        (subdomain,),
    )
    business = cur.fetchone()
    if not business:
        cur.close()
        conn.close()
        return None, None

    cur.execute(
        """
        SELECT *
        FROM business_sites
        WHERE business_id=%s
        ORDER BY created_at ASC, id ASC
        LIMIT 1
        """,
        (business["id"],),
    )
    site = cur.fetchone()
    cur.close()
    conn.close()
    return business, site


def render_site_template(slug, business, site, preview=False):
    template_path = TEMPLATE_MAP.get(slug)
    if not template_path:
        abort(404)

    business = AttrDict(business or {})
    site = AttrDict(site or {})
    if site and site.get("font_style") and not site.get("font_family"):
        site["font_family"] = FONT_STYLE_MAP.get(site["font_style"], FONT_STYLE_MAP["modern"])

    html = render_template(template_path, business=business, site=site)
    if preview:
        button_html = f"""
        <a href="{url_for('builder_create_from_template', slug=slug)}"
           style="position:fixed;right:18px;bottom:18px;z-index:9999;padding:14px 18px;border-radius:999px;background:#111827;color:#ffffff;text-decoration:none;font-weight:800;box-shadow:0 18px 45px rgba(15,23,42,.28);font-family:Arial,sans-serif;">
           Use this template
        </a>
        """
        if "</body>" in html:
            html = html.replace("</body>", f"{button_html}</body>")
        else:
            html = f"{html}{button_html}"
    return html


def render_live_business_site(subdomain):
    business, site = fetch_business_site_by_subdomain(subdomain)
    if not business:
        return render_template("website_not_found.html", subdomain=subdomain), 404

    slug = (site or {}).get("template_name") or business.get("website_type") or "retail-shop"
    slug = "salon-beauty" if slug == "beauty-salon" else slug
    if slug not in TEMPLATE_MAP:
        slug = "retail-shop"
    return render_site_template(slug, business, site, preview=False)


@app.before_request
def maybe_serve_subdomain_site():
    subdomain = current_subdomain()
    if not subdomain:
        return None
    if request.path.startswith("/static/") or request.path == "/favicon.ico":
        return None
    return render_live_business_site(subdomain)


@app.route("/")
def home():
    return render_template(
        "home.html",
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/templates")
@app.route("/preview")
def template_gallery():
    return render_template(
        "template_gallery.html",
        templates=list_templates(),
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/templates/preview/<slug>")
def template_preview(slug):
    if slug not in TEMPLATE_MAP:
        abort(404)
    business, site = demo_context(slug)
    return render_site_template(slug, business, site, preview=True)


@app.route("/builder/create/<slug>", methods=["GET", "POST"])
def builder_create_from_template(slug):
    if slug not in TEMPLATE_MAP:
        abort(404)

    meta = get_template_meta(slug) or get_template_meta("retail-shop")

    if request.method == "POST":
        business_name = (request.form.get("business_name") or "").strip() or "My Business"
        owner_name = (request.form.get("owner_name") or "").strip()
        description = (request.form.get("description") or "").strip()
        town = (request.form.get("town") or "").strip() or "Windhoek"
        region = (request.form.get("region") or "").strip() or "Khomas"
        subdomain_value = (request.form.get("subdomain") or "").strip() or business_name
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        whatsapp = (request.form.get("whatsapp") or "").strip() or phone
        logo_url = upload_logo(request.files.get("logo"))

        primary_color = request.form.get("primary_color") or "#0f172a"
        secondary_color = request.form.get("secondary_color") or "#e2a93b"
        accent_color = request.form.get("accent_color") or "#f97316"
        font_style = request.form.get("font_style") or "modern"
        wallpaper_style = request.form.get("wallpaper_style") or "premium"

        conn = db()
        cur = conn.cursor()
        try:
            unique_name = unique_subdomain(cur, subdomain_value)
            live_url = f"https://{unique_name}.{BASE_DOMAIN}"

            cur.execute(
                """
                INSERT INTO business_profiles
                (
                    business_name, owner_name, category, phone, whatsapp, email,
                    logo_url, subdomain, region, town, website_type, description
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    business_name,
                    owner_name,
                    meta["category"],
                    phone,
                    whatsapp,
                    email,
                    logo_url,
                    unique_name,
                    region,
                    town,
                    meta["slug"],
                    description,
                ),
            )
            business_id = cur.fetchone()["id"]

            cur.execute(
                """
                INSERT INTO business_sites
                (
                    business_id, site_title, template_name, primary_color,
                    secondary_color, accent_color, hero_title, hero_subtitle,
                    background_image, published, font_style, wallpaper_style,
                    show_services, show_gallery, show_booking, show_whatsapp, live_url
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true, %s, %s, true, true, true, true, %s)
                RETURNING id
                """,
                (
                    business_id,
                    business_name,
                    meta["slug"],
                    primary_color,
                    secondary_color,
                    accent_color,
                    business_name,
                    description,
                    None,
                    font_style,
                    wallpaper_style,
                    live_url,
                ),
            )

            cur.execute(
                """
                INSERT INTO subscriptions (business_id, plan_name, status)
                VALUES (%s, %s, %s)
                """,
                (business_id, "free_trial", "trial"),
            )

            conn.commit()
            business_payload = {
                "business_name": business_name,
                "subdomain": unique_name,
                "town": town,
                "region": region,
                "phone": phone,
                "email": email,
            }
            site_payload = {
                "template_name": meta["slug"],
                "live_url": live_url,
            }
            sync_site_metadata_to_supabase(business_id, business_payload, site_payload)
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

        return redirect(url_for("dashboard", business_id=business_id))

    return render_template(
        "builder/create_from_template.html",
        slug=meta["slug"],
        template_meta=meta,
        region_options=REGION_OPTIONS,
        base_domain=BASE_DOMAIN,
        preview_url=url_for("template_preview", slug=meta["slug"]),
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/dashboard/<business_id>")
def dashboard(business_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_profiles WHERE id=%s LIMIT 1", (business_id,))
    business = cur.fetchone()
    if not business:
        cur.close()
        conn.close()
        abort(404)

    cur.execute(
        """
        SELECT *
        FROM business_sites
        WHERE business_id=%s
        ORDER BY created_at ASC, id ASC
        LIMIT 1
        """,
        (business_id,),
    )
    site = cur.fetchone()
    cur.execute(
        """
        SELECT *
        FROM subscriptions
        WHERE business_id=%s
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (business_id,),
    )
    subscription = cur.fetchone()
    cur.close()
    conn.close()

    return render_template(
        "dashboard.html",
        business=business,
        site=site,
        subscription=subscription,
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/site/<subdomain>")
def local_site_preview(subdomain):
    return render_live_business_site(subdomain)


@app.route("/register")
def register():
    return redirect(url_for("template_gallery"))


@app.route("/builder/new")
def new_website_builder():
    return redirect(url_for("template_gallery"))


@app.route("/dashboard/<business_id>/upgrade")
def upgrade_business(business_id):
    return render_template("upgrade.html", business_id=business_id)


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/packages")
@app.route("/support")
def simple_pages():
    return render_template(
        "home.html",
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/healthz")
def healthz():
    return {
        "status": "ok",
        "app": os.getenv("APP_NAME", "VibeHost"),
        "domain": BASE_DOMAIN,
        "support_phone": SUPPORT_PHONE,
    }


@app.route("/favicon.ico")
def favicon():
    return "", 204


if __name__ == "__main__":
    app.run(debug=True, port=5055)
