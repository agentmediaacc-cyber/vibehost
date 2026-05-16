import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps
from io import BytesIO
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
except Exception:
    canvas = None

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
TRIAL_DAYS = 14
OWNER_PRODUCT_LIMIT = 3
OWNER_DOCUMENT_LIMIT = 10
FREE_TOOL_DOCUMENT_LIMIT = 2

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
    {"name": "Retail Shop", "slug": "retail-shop", "category": "retail", "description": "Product catalog, featured deals, WhatsApp orders and a polished storefront."},
    {"name": "Restaurant and Food", "slug": "restaurant-food", "category": "food", "description": "Menus, meal promotions, delivery flow and table or catering enquiries."},
    {"name": "Transport and Shuttle", "slug": "transport-shuttle", "category": "transport", "description": "Airport transfers, route cards, booking requests and operator tools."},
    {"name": "Guesthouse and Lodge", "slug": "guesthouse-lodge", "category": "hospitality", "description": "Room previews, stay enquiries, amenity highlights and booking prompts."},
    {"name": "Salon and Beauty", "slug": "salon-beauty", "category": "beauty", "description": "Hair, nails, makeup and appointment-driven service presentation."},
    {"name": "School and Education", "slug": "school-education", "category": "education", "description": "Admissions, parent communication, notices and academic feature blocks."},
    {"name": "Health and Wellness", "slug": "health-wellness", "category": "health", "description": "Consultation enquiries, wellness services and clinic-style credibility."},
    {"name": "Construction and Repair", "slug": "construction", "category": "construction", "description": "Project showcases, quotation flows and contractor-oriented service pages."},
    {"name": "Cleaning Services", "slug": "cleaning-services", "category": "services", "description": "Recurring plans, quote requests, service packages and cleaning teams."},
]

REGION_OPTIONS = [
    "Khomas", "Erongo", "Oshana", "Ohangwena", "Omusati", "Oshikoto", "Otjozondjupa",
    "Kunene", "Hardap", "Karas", "Kavango East", "Kavango West", "Zambezi", "Omaheke",
]

FONT_STYLE_MAP = {
    "modern": "Inter, Arial, sans-serif",
    "luxury": "Georgia, 'Times New Roman', serif",
    "friendly": "'Trebuchet MS', Verdana, sans-serif",
}

WEBSITE_TYPE_LABELS = {
    "retail-shop": "products",
    "restaurant-food": "menu items",
    "transport-shuttle": "routes/services",
    "guesthouse-lodge": "rooms",
    "salon-beauty": "beauty services",
    "school-education": "programs",
    "health-wellness": "services",
    "construction": "project services",
    "cleaning-services": "packages",
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


def now_utc():
    return datetime.now(timezone.utc)


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def decimal_value(value, default="0"):
    raw = str(value or default).strip()
    try:
        return Decimal(raw)
    except (InvalidOperation, TypeError):
        return Decimal(str(default))


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


def template_slug(slug):
    return "salon-beauty" if slug == "beauty-salon" else slug


def get_template_meta(slug):
    canonical_slug = template_slug(slug)
    for row in TEMPLATE_ROWS:
        if row["slug"] == canonical_slug:
            return row
    return None


def list_templates():
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT name, slug, category, description FROM website_templates WHERE active=true ORDER BY name")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        if rows:
            return rows
    except Exception:
        pass
    return TEMPLATE_ROWS


def upload_logo(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    filename = f"{uuid.uuid4().hex}_{secure_filename(file_storage.filename)}"
    file_storage.save(UPLOAD_FOLDER / filename)
    return f"/static/uploads/{filename}"


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


def safe_supabase_insert(table_name, payload):
    client = supabase_client()
    if not client:
        return
    try:
        client.table(table_name).upsert(payload).execute()
    except Exception as exc:
        logger.warning("Supabase insert failed for %s: %s", table_name, exc)


def website_item_label(website_type):
    return WEBSITE_TYPE_LABELS.get(template_slug(website_type or ""), "products/services")


def demo_context(slug):
    meta = get_template_meta(slug) or get_template_meta("retail-shop")
    business = AttrDict(
        {
            "business_name": "VibeHost Demo Store",
            "owner_name": "VibeHost Business",
            "description": f"Preview the full {meta['name']} template with neutral example content before launching your live website.",
            "town": "Windhoek",
            "region": "Khomas",
            "email": "hello@vibehostdemo.com",
            "phone": "+264 81 000 0000",
            "whatsapp": "264810000000",
            "logo_url": None,
            "subdomain": "vibehost-demo",
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
            "hero_title": "VibeHost Demo Store",
            "hero_subtitle": business["description"],
            "font_style": "modern",
            "font_family": FONT_STYLE_MAP["modern"],
            "wallpaper_style": "premium",
            "live_url": f"https://vibehost-demo.{BASE_DOMAIN}",
            "published": True,
        }
    )
    return business, site


def render_site_template(slug, business, site, preview=False):
    template_path = TEMPLATE_MAP.get(template_slug(slug))
    if not template_path:
        abort(404)
    business = AttrDict(business or {})
    site = AttrDict(site or {})
    if site.get("font_style") and not site.get("font_family"):
        site["font_family"] = FONT_STYLE_MAP.get(site["font_style"], FONT_STYLE_MAP["modern"])
    html = render_template(template_path, business=business, site=site)
    if preview:
        button_html = f"""
        <a href="{url_for('builder_create_from_template', slug=template_slug(slug))}"
           style="position:fixed;right:18px;bottom:18px;z-index:9999;padding:14px 18px;border-radius:999px;background:#111827;color:#ffffff;text-decoration:none;font-weight:800;box-shadow:0 18px 45px rgba(15,23,42,.28);font-family:Arial,sans-serif;">
           Use this template
        </a>
        """
        html = html.replace("</body>", f"{button_html}</body>") if "</body>" in html else f"{html}{button_html}"
    return html


def fetch_business_site_by_subdomain(subdomain):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_profiles WHERE subdomain=%s LIMIT 1", (subdomain,))
    business = cur.fetchone()
    if not business:
        cur.close()
        conn.close()
        return None, None
    cur.execute("SELECT * FROM business_sites WHERE business_id=%s ORDER BY created_at ASC, id ASC LIMIT 1", (business["id"],))
    site = cur.fetchone()
    cur.close()
    conn.close()
    return business, site


def render_live_business_site(subdomain):
    business, site = fetch_business_site_by_subdomain(subdomain)
    if not business:
        return render_template("website_not_found.html", subdomain=subdomain), 404
    slug = template_slug((site or {}).get("template_name") or business.get("website_type") or "retail-shop")
    if slug not in TEMPLATE_MAP:
        slug = "retail-shop"
    return render_site_template(slug, business, site, preview=False)


def trial_status_info(subscription):
    started = parse_dt((subscription or {}).get("trial_started_at"))
    expires = parse_dt((subscription or {}).get("trial_expires_at"))
    current = now_utc()
    if not started:
        started = current
    if not expires:
        expires = started + timedelta(days=TRIAL_DAYS)
    days_left = max(0, (expires.date() - current.date()).days)
    expired = current > expires and (subscription or {}).get("status") == "trial"
    return {
        "started": started,
        "expires": expires,
        "days_left": days_left,
        "expired": expired,
    }


def owner_logged_in():
    return bool(session.get("owner_id") and session.get("business_id"))


def free_tool_logged_in():
    return bool(session.get("free_tool_user_id"))


def owner_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not owner_logged_in():
            return redirect(url_for("owner_login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def free_tool_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not free_tool_logged_in():
            return redirect(url_for("free_tools_login"))
        return view_func(*args, **kwargs)
    return wrapped


def get_owner_context():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_owners WHERE id=%s LIMIT 1", (session["owner_id"],))
    owner = cur.fetchone()
    cur.execute("SELECT * FROM business_profiles WHERE id=%s LIMIT 1", (session["business_id"],))
    business = cur.fetchone()
    cur.execute("SELECT * FROM business_sites WHERE business_id=%s ORDER BY created_at ASC, id ASC LIMIT 1", (session["business_id"],))
    site = cur.fetchone()
    cur.execute("SELECT * FROM subscriptions WHERE business_id=%s ORDER BY created_at DESC, id DESC LIMIT 1", (session["business_id"],))
    subscription = cur.fetchone()
    cur.close()
    conn.close()
    if not owner or not business:
        session.pop("owner_id", None)
        session.pop("business_id", None)
        abort(403)
    trial = trial_status_info(subscription)
    return owner, business, site, subscription, trial


def get_free_tool_user():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM free_tool_users WHERE id=%s LIMIT 1", (session["free_tool_user_id"],))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if not user:
        session.pop("free_tool_user_id", None)
        abort(403)
    return user


def owner_write_blocked(trial):
    return trial["expired"]


def owner_dashboard_stats(business_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS count FROM business_products WHERE business_id=%s AND status='active'", (business_id,))
    products = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) AS count FROM business_orders WHERE business_id=%s", (business_id,))
    orders = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) AS count FROM business_documents WHERE business_id=%s AND document_type='invoice'", (business_id,))
    invoices = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) AS count FROM business_documents WHERE business_id=%s AND document_type='quotation'", (business_id,))
    quotations = cur.fetchone()["count"]
    cur.close()
    conn.close()
    return {"products": products, "orders": orders, "invoices": invoices, "quotations": quotations}


def create_document(cur, business_id, document_type, form_data):
    quantity = decimal_value(form_data.get("quantity"), "1")
    unit_price = decimal_value(form_data.get("unit_price"), "0")
    subtotal = quantity * unit_price
    tax = decimal_value(form_data.get("tax"), "0")
    total = subtotal + tax
    number_prefix = "INV" if document_type == "invoice" else "QUO"
    document_number = f"{number_prefix}-{slugify(str(uuid.uuid4())[:8]).upper()}"
    cur.execute(
        """
        INSERT INTO business_documents
        (business_id, document_type, document_number, customer_name, customer_email,
         customer_phone, notes, subtotal, tax, total, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (
            business_id,
            document_type,
            document_number,
            (form_data.get("customer_name") or "").strip(),
            (form_data.get("customer_email") or "").strip(),
            (form_data.get("customer_phone") or "").strip(),
            (form_data.get("notes") or "").strip(),
            subtotal,
            tax,
            total,
            (form_data.get("status") or "draft").strip() or "draft",
        ),
    )
    document_id = cur.fetchone()["id"]
    cur.execute(
        """
        INSERT INTO business_document_items
        (document_id, item_name, quantity, unit_price, total)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (
            document_id,
            (form_data.get("item_name") or "Service item").strip(),
            quantity,
            unit_price,
            subtotal,
        ),
    )
    return document_id


def fetch_document(document_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_documents WHERE id=%s LIMIT 1", (document_id,))
    document = cur.fetchone()
    if not document:
        cur.close()
        conn.close()
        return None, []
    cur.execute("SELECT * FROM business_document_items WHERE document_id=%s ORDER BY created_at ASC, id ASC", (document_id,))
    items = cur.fetchall()
    cur.close()
    conn.close()
    return document, items


def document_pdf_response(business, document, items):
    if canvas is None:
        html = render_template("owner/document_download_fallback.html", business=business, document=document, items=items)
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.rect(0, height - 55 * mm, width, 55 * mm, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(18 * mm, height - 20 * mm, "VibeHost")
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(18 * mm, height - 33 * mm, business["business_name"])
    pdf.setFont("Helvetica", 11)
    pdf.drawString(18 * mm, height - 42 * mm, f"{document['document_type'].title()}  {document['document_number']}")
    pdf.drawString(18 * mm, height - 49 * mm, f"Status: {document['status']}")

    y = height - 72 * mm
    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(18 * mm, y, "Customer")
    pdf.setFont("Helvetica", 11)
    y -= 7 * mm
    pdf.drawString(18 * mm, y, document.get("customer_name") or "Not provided")
    y -= 6 * mm
    pdf.drawString(18 * mm, y, document.get("customer_email") or "")
    y -= 6 * mm
    pdf.drawString(18 * mm, y, document.get("customer_phone") or "")

    y -= 14 * mm
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(18 * mm, y, "Item")
    pdf.drawString(115 * mm, y, "Qty")
    pdf.drawString(140 * mm, y, "Unit")
    pdf.drawString(170 * mm, y, "Total")
    y -= 4 * mm
    pdf.line(18 * mm, y, 192 * mm, y)
    y -= 8 * mm
    pdf.setFont("Helvetica", 11)
    for item in items:
        pdf.drawString(18 * mm, y, str(item.get("item_name") or "Item"))
        pdf.drawRightString(130 * mm, y, str(item.get("quantity") or 1))
        pdf.drawRightString(158 * mm, y, f"N$ {item.get('unit_price') or 0}")
        pdf.drawRightString(192 * mm, y, f"N$ {item.get('total') or 0}")
        y -= 8 * mm

    y -= 8 * mm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(192 * mm, y, f"Subtotal: N$ {document.get('subtotal') or 0}")
    y -= 7 * mm
    pdf.drawRightString(192 * mm, y, f"Tax: N$ {document.get('tax') or 0}")
    y -= 7 * mm
    pdf.drawRightString(192 * mm, y, f"Total: N$ {document.get('total') or 0}")
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer.getvalue(), 200, {
        "Content-Type": "application/pdf",
        "Content-Disposition": f"inline; filename={document['document_number']}.pdf",
    }


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
    return render_template("home.html", support_phone=SUPPORT_PHONE, support_whatsapp_url=SUPPORT_WHATSAPP_URL)


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
    slug = template_slug(slug)
    if slug not in TEMPLATE_MAP:
        abort(404)
    business, site = demo_context(slug)
    return render_site_template(slug, business, site, preview=True)


@app.route("/builder/create/<slug>", methods=["GET", "POST"])
def builder_create_from_template(slug):
    slug = template_slug(slug)
    if slug not in TEMPLATE_MAP:
        abort(404)
    meta = get_template_meta(slug) or get_template_meta("retail-shop")
    errors = []

    if request.method == "POST":
        business_name = (request.form.get("business_name") or "").strip() or "VibeHost Business"
        owner_name = (request.form.get("owner_name") or "").strip()
        description = (request.form.get("description") or "").strip()
        town = (request.form.get("town") or "").strip() or "Windhoek"
        region = (request.form.get("region") or "").strip() or "Khomas"
        subdomain_value = (request.form.get("subdomain") or "").strip() or business_name
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        whatsapp = (request.form.get("whatsapp") or "").strip() or phone
        owner_email = (request.form.get("owner_email") or "").strip().lower()
        owner_password = request.form.get("owner_password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        logo_url = upload_logo(request.files.get("logo"))
        primary_color = request.form.get("primary_color") or "#0f172a"
        secondary_color = request.form.get("secondary_color") or "#e2a93b"
        accent_color = request.form.get("accent_color") or "#f97316"
        font_style = request.form.get("font_style") or "modern"
        wallpaper_style = request.form.get("wallpaper_style") or "premium"

        if not owner_email:
            errors.append("Owner login email is required.")
        if len(owner_password) < 8:
            errors.append("Owner password must be at least 8 characters.")
        if owner_password != confirm_password:
            errors.append("Owner password and confirm password must match.")

        if not errors:
            conn = db()
            cur = conn.cursor()
            try:
                cur.execute("SELECT id FROM business_owners WHERE email=%s LIMIT 1", (owner_email,))
                if cur.fetchone():
                    errors.append("That owner login email is already in use.")
                else:
                    unique_name = unique_subdomain(cur, subdomain_value)
                    live_url = f"https://{unique_name}.{BASE_DOMAIN}"
                    trial_started_at = now_utc()
                    trial_expires_at = trial_started_at + timedelta(days=TRIAL_DAYS)

                    cur.execute(
                        """
                        INSERT INTO business_profiles
                        (business_name, owner_name, category, phone, whatsapp, email, logo_url,
                         subdomain, region, town, website_type, description)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        RETURNING id
                        """,
                        (
                            business_name, owner_name, meta["category"], phone, whatsapp, email,
                            logo_url, unique_name, region, town, meta["slug"], description,
                        ),
                    )
                    business_id = cur.fetchone()["id"]

                    cur.execute(
                        """
                        INSERT INTO business_sites
                        (business_id, site_title, template_name, primary_color, secondary_color,
                         accent_color, hero_title, hero_subtitle, background_image, published,
                         font_style, wallpaper_style, show_services, show_gallery, show_booking,
                         show_whatsapp, live_url)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,true,%s,%s,true,true,true,true,%s)
                        RETURNING id
                        """,
                        (
                            business_id, business_name, meta["slug"], primary_color, secondary_color,
                            accent_color, business_name, description or f"Welcome to {business_name}", None,
                            font_style, wallpaper_style, live_url,
                        ),
                    )
                    site_id = cur.fetchone()["id"]

                    cur.execute(
                        """
                        INSERT INTO subscriptions
                        (business_id, plan_name, status, trial_started_at, trial_expires_at)
                        VALUES (%s,%s,%s,%s,%s)
                        RETURNING id
                        """,
                        (business_id, "free_trial", "trial", trial_started_at, trial_expires_at),
                    )
                    cur.fetchone()

                    cur.execute(
                        """
                        INSERT INTO business_owners
                        (business_id, owner_name, email, password_hash, role)
                        VALUES (%s,%s,%s,%s,%s)
                        RETURNING id
                        """,
                        (business_id, owner_name or business_name, owner_email, generate_password_hash(owner_password), "owner"),
                    )
                    owner_id = cur.fetchone()["id"]
                    conn.commit()

                    safe_supabase_insert(
                        "vibehost_sites",
                        {
                            "business_id": str(business_id),
                            "business_name": business_name,
                            "subdomain": unique_name,
                            "live_url": live_url,
                            "template_name": meta["slug"],
                            "owner_email": owner_email,
                        },
                    )
                    safe_supabase_insert(
                        "vibehost_owners",
                        {
                            "business_id": str(business_id),
                            "owner_email": owner_email,
                            "role": "owner",
                        },
                    )

                    session["owner_id"] = str(owner_id)
                    session["business_id"] = str(business_id)
                    return redirect(url_for("dashboard", business_id=business_id))
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
                conn.close()

    return render_template(
        "builder/create_from_template.html",
        slug=meta["slug"],
        template_meta=meta,
        region_options=REGION_OPTIONS,
        base_domain=BASE_DOMAIN,
        preview_url=url_for("template_preview", slug=meta["slug"]),
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
        errors=errors,
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
    cur.execute("SELECT * FROM business_sites WHERE business_id=%s ORDER BY created_at ASC, id ASC LIMIT 1", (business_id,))
    site = cur.fetchone()
    cur.execute("SELECT * FROM subscriptions WHERE business_id=%s ORDER BY created_at DESC, id DESC LIMIT 1", (business_id,))
    subscription = cur.fetchone()
    cur.execute("SELECT * FROM business_owners WHERE business_id=%s ORDER BY created_at ASC, id ASC LIMIT 1", (business_id,))
    owner = cur.fetchone()
    cur.close()
    conn.close()
    trial = trial_status_info(subscription)
    return render_template(
        "dashboard.html",
        business=business,
        site=site,
        subscription=subscription,
        owner=owner,
        trial=trial,
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/owner/login", methods=["GET", "POST"])
def owner_login():
    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM business_owners WHERE email=%s LIMIT 1", (email,))
        owner = cur.fetchone()
        cur.close()
        conn.close()
        if owner and check_password_hash(owner["password_hash"], password):
            session["owner_id"] = str(owner["id"])
            session["business_id"] = str(owner["business_id"])
            return redirect(request.args.get("next") or url_for("owner_dashboard"))
        error = "Invalid email or password."
    return render_template("owner/login.html", error=error, support_phone=SUPPORT_PHONE, support_whatsapp_url=SUPPORT_WHATSAPP_URL)


@app.route("/owner/logout")
def owner_logout():
    session.pop("owner_id", None)
    session.pop("business_id", None)
    return redirect(url_for("owner_login"))


@app.route("/owner/dashboard")
@owner_required
def owner_dashboard():
    owner, business, site, subscription, trial = get_owner_context()
    stats = owner_dashboard_stats(business["id"])
    return render_template(
        "owner/dashboard.html",
        owner=owner,
        business=business,
        site=site,
        subscription=subscription,
        trial=trial,
        stats=stats,
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/owner/site-editor", methods=["GET", "POST"])
@owner_required
def owner_site_editor():
    owner, business, site, subscription, trial = get_owner_context()
    error = None
    success = None
    if request.method == "POST":
        if owner_write_blocked(trial):
            error = "Your 14-day trial has ended. Upgrade to continue editing your website."
        else:
            logo_url = upload_logo(request.files.get("logo")) or business.get("logo_url")
            conn = db()
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE business_profiles
                SET business_name=%s, description=%s, town=%s, region=%s, phone=%s,
                    whatsapp=%s, email=%s, logo_url=%s
                WHERE id=%s
                """,
                (
                    (request.form.get("business_name") or business["business_name"]).strip(),
                    (request.form.get("description") or "").strip(),
                    (request.form.get("town") or "").strip(),
                    (request.form.get("region") or "").strip(),
                    (request.form.get("phone") or "").strip(),
                    (request.form.get("whatsapp") or "").strip(),
                    (request.form.get("email") or "").strip(),
                    logo_url,
                    business["id"],
                ),
            )
            cur.execute(
                """
                UPDATE business_sites
                SET primary_color=%s, secondary_color=%s, accent_color=%s, hero_title=%s,
                    hero_subtitle=%s, font_style=%s, wallpaper_style=%s
                WHERE business_id=%s
                """,
                (
                    request.form.get("primary_color") or site.get("primary_color"),
                    request.form.get("secondary_color") or site.get("secondary_color"),
                    request.form.get("accent_color") or site.get("accent_color"),
                    (request.form.get("hero_title") or "").strip(),
                    (request.form.get("hero_subtitle") or "").strip(),
                    request.form.get("font_style") or site.get("font_style"),
                    request.form.get("wallpaper_style") or site.get("wallpaper_style"),
                    business["id"],
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
            success = "Website content updated successfully."
            owner, business, site, subscription, trial = get_owner_context()
    return render_template(
        "owner/site_editor.html",
        owner=owner,
        business=business,
        site=site,
        trial=trial,
        error=error,
        success=success,
        region_options=REGION_OPTIONS,
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/owner/products", methods=["GET", "POST"])
@owner_required
def owner_products():
    owner, business, site, subscription, trial = get_owner_context()
    error = None
    success = None
    if request.method == "POST":
        if owner_write_blocked(trial):
            error = "Your 14-day trial has ended. Upgrade to continue editing your website."
        else:
            conn = db()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS count FROM business_products WHERE business_id=%s AND status='active'", (business["id"],))
            active_count = cur.fetchone()["count"]
            if subscription and subscription.get("status") == "trial" and active_count >= OWNER_PRODUCT_LIMIT:
                error = "Free trial websites can only keep 3 active products/services. Upgrade to add more."
            else:
                image_url = upload_logo(request.files.get("image"))
                cur.execute(
                    """
                    INSERT INTO business_products
                    (business_id, name, description, category, price, image_url, stock_quantity, status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        business["id"],
                        (request.form.get("name") or "").strip(),
                        (request.form.get("description") or "").strip(),
                        (request.form.get("category") or "").strip(),
                        decimal_value(request.form.get("price"), "0"),
                        image_url,
                        int(request.form.get("stock_quantity") or 0),
                        "active",
                    ),
                )
                conn.commit()
                success = f"{website_item_label(business.get('website_type')).title()} item created."
            cur.close()
            conn.close()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_products WHERE business_id=%s ORDER BY created_at DESC", (business["id"],))
    products = cur.fetchall()
    cur.close()
    conn.close()
    return render_template(
        "owner/products.html",
        owner=owner,
        business=business,
        site=site,
        trial=trial,
        products=products,
        item_label=website_item_label(business.get("website_type")),
        error=error,
        success=success,
    )


@app.route("/owner/products/<product_id>/delete", methods=["POST"])
@owner_required
def owner_product_delete(product_id):
    owner, business, site, subscription, trial = get_owner_context()
    if not owner_write_blocked(trial):
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE business_products SET status='archived' WHERE id=%s AND business_id=%s", (product_id, business["id"]))
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for("owner_products"))


@app.route("/owner/orders")
@owner_required
def owner_orders():
    owner, business, site, subscription, trial = get_owner_context()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_orders WHERE business_id=%s ORDER BY created_at DESC", (business["id"],))
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("owner/orders.html", owner=owner, business=business, trial=trial, orders=orders)


@app.route("/owner/orders/<order_id>/status", methods=["POST"])
@owner_required
def owner_order_status(order_id):
    owner, business, site, subscription, trial = get_owner_context()
    if not owner_write_blocked(trial):
        status = (request.form.get("status") or "new").strip()
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE business_orders SET status=%s WHERE id=%s AND business_id=%s", (status, order_id, business["id"]))
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for("owner_orders"))


@app.route("/api/public/enquiry", methods=["POST"])
def public_enquiry():
    business_id = request.form.get("business_id") or (request.json or {}).get("business_id")
    if not business_id:
        return jsonify({"ok": False, "error": "business_id is required"}), 400
    payload = request.form if request.form else (request.json or {})
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO business_orders
        (business_id, customer_name, customer_email, customer_phone, order_type, message, status, total_amount, source)
        VALUES (%s,%s,%s,%s,%s,%s,'new',%s,'website')
        RETURNING id
        """,
        (
            business_id,
            (payload.get("customer_name") or "").strip(),
            (payload.get("customer_email") or "").strip(),
            (payload.get("customer_phone") or "").strip(),
            (payload.get("order_type") or "enquiry").strip(),
            (payload.get("message") or "").strip(),
            decimal_value(payload.get("total_amount"), "0"),
        ),
    )
    order_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True, "order_id": str(order_id)})


@app.route("/owner/invoices", methods=["GET", "POST"])
@owner_required
def owner_invoices():
    return owner_documents("invoice")


@app.route("/owner/quotations", methods=["GET", "POST"])
@owner_required
def owner_quotations():
    return owner_documents("quotation")


def owner_documents(document_type):
    owner, business, site, subscription, trial = get_owner_context()
    error = None
    success = None
    if request.method == "POST":
        if owner_write_blocked(trial):
            error = "Your 14-day trial has ended. Upgrade to continue editing your website."
        else:
            conn = db()
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) AS count FROM business_documents WHERE business_id=%s AND document_type=%s",
                (business["id"], document_type),
            )
            count = cur.fetchone()["count"]
            if subscription and subscription.get("status") == "trial" and count >= OWNER_DOCUMENT_LIMIT:
                error = f"Trial websites can only keep {OWNER_DOCUMENT_LIMIT} {document_type}s. Upgrade to continue."
            else:
                create_document(cur, business["id"], document_type, request.form)
                conn.commit()
                success = f"{document_type.title()} created successfully."
            cur.close()
            conn.close()
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM business_documents WHERE business_id=%s AND document_type=%s ORDER BY created_at DESC",
        (business["id"], document_type),
    )
    documents = cur.fetchall()
    cur.close()
    conn.close()
    return render_template(
        "owner/documents.html",
        owner=owner,
        business=business,
        trial=trial,
        documents=documents,
        document_type=document_type,
        error=error,
        success=success,
    )


@app.route("/owner/documents/<document_id>")
@owner_required
def owner_document_detail(document_id):
    owner, business, site, subscription, trial = get_owner_context()
    document, items = fetch_document(document_id)
    if not document or str(document["business_id"]) != str(business["id"]):
        abort(404)
    return render_template("owner/document_detail.html", owner=owner, business=business, document=document, items=items, trial=trial)


@app.route("/owner/documents/<document_id>/download")
@owner_required
def owner_document_download(document_id):
    owner, business, site, subscription, trial = get_owner_context()
    document, items = fetch_document(document_id)
    if not document or str(document["business_id"]) != str(business["id"]):
        abort(404)
    body, status_code, headers = document_pdf_response(business, document, items)
    return body, status_code, headers


@app.route("/free-tools")
def free_tools_index():
    return render_template("free_tools/index.html", support_phone=SUPPORT_PHONE, support_whatsapp_url=SUPPORT_WHATSAPP_URL)


@app.route("/free-tools/register", methods=["GET", "POST"])
def free_tools_register():
    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        full_name = (request.form.get("full_name") or "").strip()
        if not email:
            error = "Email is required."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm_password:
            error = "Password and confirm password must match."
        else:
            conn = db()
            cur = conn.cursor()
            cur.execute("SELECT id FROM free_tool_users WHERE email=%s LIMIT 1", (email,))
            if cur.fetchone():
                error = "An account with that email already exists."
            else:
                cur.execute(
                    """
                    INSERT INTO free_tool_users (email, password_hash, full_name, provider, plan_name)
                    VALUES (%s,%s,%s,'email','free')
                    RETURNING id
                    """,
                    (email, generate_password_hash(password), full_name),
                )
                user_id = cur.fetchone()["id"]
                conn.commit()
                session["free_tool_user_id"] = str(user_id)
                cur.close()
                conn.close()
                return redirect(url_for("free_tools_dashboard"))
            cur.close()
            conn.close()
    return render_template("free_tools/auth.html", mode="register", error=error)


@app.route("/free-tools/login", methods=["GET", "POST"])
def free_tools_login():
    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM free_tool_users WHERE email=%s LIMIT 1", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["free_tool_user_id"] = str(user["id"])
            return redirect(url_for("free_tools_dashboard"))
        error = "Invalid email or password."
    return render_template("free_tools/auth.html", mode="login", error=error)


@app.route("/free-tools/logout")
def free_tools_logout():
    session.pop("free_tool_user_id", None)
    return redirect(url_for("free_tools_login"))


@app.route("/free-tools/dashboard")
@free_tool_required
def free_tools_dashboard():
    user = get_free_tool_user()
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS count FROM business_documents WHERE business_id=%s AND document_type='invoice'", (user["id"],))
    invoices = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) AS count FROM business_documents WHERE business_id=%s AND document_type='quotation'", (user["id"],))
    quotations = cur.fetchone()["count"]
    cur.close()
    conn.close()
    return render_template("free_tools/dashboard.html", user=user, invoices=invoices, quotations=quotations)


@app.route("/free-tools/invoices", methods=["GET", "POST"])
@free_tool_required
def free_tools_invoices():
    return free_tool_documents("invoice")


@app.route("/free-tools/quotations", methods=["GET", "POST"])
@free_tool_required
def free_tools_quotations():
    return free_tool_documents("quotation")


def free_tool_documents(document_type):
    user = get_free_tool_user()
    error = None
    success = None
    if request.method == "POST":
        conn = db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS count FROM business_documents WHERE business_id=%s AND document_type=%s",
            (user["id"], document_type),
        )
        count = cur.fetchone()["count"]
        if count >= FREE_TOOL_DOCUMENT_LIMIT:
            error = "Upgrade monthly to keep unlimited invoice and quotation records."
        else:
            create_document(cur, user["id"], document_type, request.form)
            conn.commit()
            success = f"{document_type.title()} created successfully."
        cur.close()
        conn.close()
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM business_documents WHERE business_id=%s AND document_type=%s ORDER BY created_at DESC",
        (user["id"], document_type),
    )
    documents = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("free_tools/documents.html", user=user, documents=documents, document_type=document_type, error=error, success=success)


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
    return redirect(url_for("owner_login"))


@app.route("/packages")
@app.route("/support")
def simple_pages():
    return render_template("home.html", support_phone=SUPPORT_PHONE, support_whatsapp_url=SUPPORT_WHATSAPP_URL)


@app.route("/healthz")
def healthz():
    return {"status": "ok", "app": os.getenv("APP_NAME", "VibeHost"), "domain": BASE_DOMAIN, "support_phone": SUPPORT_PHONE}


@app.route("/favicon.ico")
def favicon():
    return "", 204


if __name__ == "__main__":
    app.run(debug=True, port=5055)
