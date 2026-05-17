import logging
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps
from io import BytesIO
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, session, url_for
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

for _site_packages in sorted((Path("venv/lib")).glob("python*/site-packages")):
    site_packages_path = str(_site_packages.resolve())
    if site_packages_path not in sys.path:
        sys.path.append(site_packages_path)

from services.pdf_service import generate_document_pdf

try:
    import reportlab  # noqa: F401
except Exception:
    reportlab = None

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

DOCUMENT_TEMPLATE_ROWS = {
    "invoice": [
        {"slug": "invoice_modern_clean", "name": "Modern Clean", "best_for": "Consultants, startups and service professionals"},
        {"slug": "invoice_luxury_gold", "name": "Luxury Gold", "best_for": "Premium brands, designers and boutiques"},
        {"slug": "invoice_corporate_blue", "name": "Corporate Blue", "best_for": "Agencies, offices and B2B businesses"},
        {"slug": "invoice_retail_receipt", "name": "Retail Receipt", "best_for": "Shops, mini-markets and cash-sale businesses"},
        {"slug": "invoice_restaurant_order", "name": "Restaurant Order", "best_for": "Food businesses, cafes and catering teams"},
        {"slug": "invoice_transport_trip", "name": "Transport Trip", "best_for": "Shuttles, logistics and travel operators"},
        {"slug": "invoice_construction_progress", "name": "Construction Progress", "best_for": "Builders, project teams and contractors"},
        {"slug": "invoice_medical_statement", "name": "Medical Statement", "best_for": "Clinics, wellness centers and practitioners"},
        {"slug": "invoice_school_fees", "name": "School Fees", "best_for": "Schools, tutors and training providers"},
        {"slug": "invoice_minimal_black", "name": "Minimal Black", "best_for": "Bold monochrome billing"},
    ],
    "quotation": [
        {"slug": "quotation_modern_clean", "name": "Modern Clean", "best_for": "Consultants, startups and service professionals"},
        {"slug": "quotation_luxury_gold", "name": "Luxury Gold", "best_for": "Premium brands, designers and boutiques"},
        {"slug": "quotation_corporate_blue", "name": "Corporate Blue", "best_for": "Agencies, offices and B2B businesses"},
        {"slug": "quotation_retail_quote", "name": "Retail Quote", "best_for": "Shops, wholesalers and supply businesses"},
        {"slug": "quotation_restaurant_catering", "name": "Restaurant Catering", "best_for": "Food businesses, events and catering teams"},
        {"slug": "quotation_transport_trip", "name": "Transport Trip", "best_for": "Shuttles, logistics and travel operators"},
        {"slug": "quotation_construction_estimate", "name": "Construction Estimate", "best_for": "Builders, project teams and contractors"},
        {"slug": "quotation_medical_plan", "name": "Medical Plan", "best_for": "Clinics, wellness plans and treatment quotes"},
        {"slug": "quotation_school_fees", "name": "School Fees", "best_for": "Schools, tutors and training providers"},
        {"slug": "quotation_minimal_black", "name": "Minimal Black", "best_for": "Bold monochrome quotations"},
    ],
}


class AttrDict(dict):
    def __getattr__(self, key):
        return self.get(key)

def master_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("master_admin_id"):
            return redirect(url_for("owner_login"))
        return f(*args, **kwargs)
    return decorated_function


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
(UPLOAD_FOLDER / "verifications").mkdir(parents=True, exist_ok=True)
(UPLOAD_FOLDER / "logos").mkdir(parents=True, exist_ok=True)
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
    forced = (request.args.get("subdomain") or "").strip().lower()
    if forced:
        return slugify(forced)
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


ALLOWED_VERIFICATION_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
SUBDOMAIN_APP_PREFIXES = (
    "/static/",
    "/favicon.ico",
    "/customer/",
    "/api/public/enquiry",
    "/healthz",
)


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


def allowed_extension(filename, allowed_extensions):
    filename = filename or ""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def upload_logo(file_storage, subdir=None, allowed_extensions=None):
    if not file_storage or not file_storage.filename:
        return None
    allowed_extensions = allowed_extensions or {"png", "jpg", "jpeg", "gif", "webp", "pdf"}
    if not allowed_extension(file_storage.filename, allowed_extensions):
        return None
    filename = f"{uuid.uuid4().hex}_{secure_filename(file_storage.filename)}"
    target_dir = UPLOAD_FOLDER / subdir if subdir else UPLOAD_FOLDER
    target_dir.mkdir(parents=True, exist_ok=True)
    file_storage.save(target_dir / filename)
    if subdir:
        return f"/static/uploads/{subdir}/{filename}"
    return f"/static/uploads/{filename}"


def uploaded_file_path(upload_url):
    if not upload_url or not str(upload_url).startswith("/static/uploads/"):
        return None
    relative = str(upload_url).replace("/static/uploads/", "", 1)
    target = (UPLOAD_FOLDER / relative).resolve()
    try:
        target.relative_to(UPLOAD_FOLDER.resolve())
    except ValueError:
        return None
    return target if target.exists() else None


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


def free_tool_template_meta(slug, document_type=None):
    if document_type:
        for row in DOCUMENT_TEMPLATE_ROWS.get(document_type, []):
            if row["slug"] == slug:
                return row
        return None
    for rows in DOCUMENT_TEMPLATE_ROWS.values():
        for row in rows:
            if row["slug"] == slug:
                return row
    return None


def free_tool_templates(document_type):
    return DOCUMENT_TEMPLATE_ROWS.get(document_type, [])


def template_doc_type_from_slug(slug):
    if str(slug).startswith("quotation_"):
        return "quotation"
    return "invoice"


def normalize_document_template(document_type, template_slug):
    document_type = document_type if document_type in {"invoice", "quotation"} else template_doc_type_from_slug(template_slug or "")
    if free_tool_template_meta(template_slug, document_type):
        return document_type, template_slug
    fallback = free_tool_templates(document_type)[0]["slug"]
    return document_type, fallback


def document_layout_key(template_slug):
    parts = str(template_slug or "").split("_", 1)
    return parts[1] if len(parts) == 2 else "modern_clean"


def document_template_path(document_type, template_slug):
    normalize_document_template(document_type, template_slug)
    return "free_tools/document_templates/document_layout.html"


def auth_provider_available(_provider):
    return bool(os.getenv("SUPABASE_URL") and (os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")) and create_client is not None)


def compute_document_lines(form_data):
    names = request.form.getlist("item_name") if request else []
    quantities = request.form.getlist("quantity") if request else []
    prices = request.form.getlist("unit_price") if request else []
    if not names and form_data:
        if hasattr(form_data, "getlist"):
            names = form_data.getlist("item_name")
            quantities = form_data.getlist("quantity")
            prices = form_data.getlist("unit_price")
        else:
            raw_names = form_data.get("item_name")
            raw_quantities = form_data.get("quantity")
            raw_prices = form_data.get("unit_price")
            names = raw_names if isinstance(raw_names, list) else [raw_names]
            quantities = raw_quantities if isinstance(raw_quantities, list) else [raw_quantities]
            prices = raw_prices if isinstance(raw_prices, list) else [raw_prices]
    items = []
    max_len = max(len(names), len(quantities), len(prices), 0)
    for idx in range(max_len):
        item_name = str(names[idx] if idx < len(names) else "").strip() if names else ""
        if not item_name:
            continue
        quantity = decimal_value(quantities[idx] if idx < len(quantities) else "1", "1")
        unit_price = decimal_value(prices[idx] if idx < len(prices) else "0", "0")
        line_total = quantity * unit_price
        items.append(
            {
                "item_name": item_name,
                "quantity": quantity,
                "unit_price": unit_price,
                "total": line_total,
            }
        )
    if not items:
        items.append({"item_name": "Service item", "quantity": Decimal("1"), "unit_price": Decimal("0"), "total": Decimal("0")})
    return items


def compute_document_totals(items, tax_percent, discount):
    subtotal = sum((item["total"] for item in items), Decimal("0"))
    tax_percentage = decimal_value(tax_percent, "0")
    discount_value = decimal_value(discount, "0")
    tax_amount = (subtotal * tax_percentage) / Decimal("100")
    total = subtotal + tax_amount - discount_value
    if total < 0:
        total = Decimal("0")
    return subtotal, tax_amount, discount_value, total


def format_money(value):
    amount = decimal_value(value, "0")
    return f"{amount:,.2f}"

def document_business_block(source):
    return {
        "business_name": source.get("business_name") or "VibeHost Business",
        "business_logo_url": source.get("business_logo_url"),
        "business_email": source.get("business_email") or source.get("email") or "",
        "business_phone": source.get("business_phone") or source.get("phone") or "",
        "business_address": source.get("business_address") or source.get("address") or "",
        "business_tax_number": source.get("business_tax_number") or "",
        "payment_details": source.get("payment_details") or "",
    }


def build_document_context(template_slug, document_type="invoice", business_data=None, watermark=True, form_data=None, saved_document=None, saved_items=None):
    document_type, template_slug = normalize_document_template(document_type, template_slug)
    meta = free_tool_template_meta(template_slug, document_type) or free_tool_templates(document_type)[0]
    if saved_document:
        items = [
            {
                "item_name": item.get("item_name"),
                "quantity": decimal_value(item.get("quantity"), "1"),
                "unit_price": decimal_value(item.get("unit_price"), "0"),
                "total": decimal_value(item.get("total"), "0"),
            }
            for item in (saved_items or [])
        ]
        subtotal = decimal_value(saved_document.get("subtotal"), "0")
        tax = decimal_value(saved_document.get("tax"), "0")
        discount = decimal_value(saved_document.get("discount"), "0")
        total = decimal_value(saved_document.get("total"), "0")
        issue_date = saved_document.get("issue_date") or parse_dt(saved_document.get("created_at")) or now_utc()
        context = {
            "template_meta": meta,
            "template_slug": template_slug,
            "layout_key": document_layout_key(template_slug),
            "document_type": saved_document.get("document_type", document_type),
            "document_number": saved_document.get("document_number", "INV-0001"),
            **document_business_block(saved_document),
            "customer_name": saved_document.get("customer_name") or "Customer Name",
            "customer_email": saved_document.get("customer_email") or "customer@example.com",
            "customer_phone": saved_document.get("customer_phone") or "+264 81 000 0000",
            "customer_address": saved_document.get("customer_address") or "",
            "notes": saved_document.get("notes") or "",
            "terms": saved_document.get("terms") or "",
            "issue_date": parse_dt(issue_date),
            "due_date": parse_dt(saved_document.get("due_date")),
            "valid_until": parse_dt(saved_document.get("valid_until")),
            "items": items,
            "subtotal": subtotal,
            "tax": tax,
            "discount": discount,
            "total": total,
            "watermark": bool(saved_document.get("watermark")) if saved_document.get("watermark") is not None else watermark,
        }
        return context

    form_data = form_data or {}
    items = compute_document_lines(form_data)
    subtotal, tax, discount, total = compute_document_totals(items, form_data.get("tax_percentage"), form_data.get("discount"))
    business_data = business_data or {}
    issue_date = form_data.get("issue_date") or now_utc().date().isoformat()
    return {
        "template_meta": meta,
        "template_slug": template_slug,
        "layout_key": document_layout_key(template_slug),
        "document_type": (form_data.get("document_type") or document_type),
        "document_number": form_data.get("document_number") or f"{'INV' if (form_data.get('document_type') or document_type) == 'invoice' else 'QUO'}-SAMPLE",
        **document_business_block({
            **business_data,
            "business_name": form_data.get("business_name") or business_data.get("business_name") or "VibeHost Business",
            "business_logo_url": business_data.get("business_logo_url"),
            "business_email": form_data.get("business_email") or business_data.get("business_email"),
            "business_phone": form_data.get("business_phone") or business_data.get("business_phone"),
            "business_address": form_data.get("business_address") or business_data.get("business_address"),
            "business_tax_number": form_data.get("business_tax_number") or business_data.get("business_tax_number"),
            "payment_details": form_data.get("payment_details") or business_data.get("payment_details"),
        }),
        "customer_name": form_data.get("customer_name") or "Customer Name",
        "customer_email": form_data.get("customer_email") or "customer@example.com",
        "customer_phone": form_data.get("customer_phone") or "+264 81 000 0000",
        "customer_address": form_data.get("customer_address") or "",
        "notes": form_data.get("notes") or "Add delivery notes, payment terms or service details here.",
        "terms": form_data.get("terms") or "Payment is due according to the terms shown on this document.",
        "issue_date": parse_dt(issue_date),
        "due_date": parse_dt(form_data.get("due_date")),
        "valid_until": parse_dt(form_data.get("valid_until")),
        "items": items,
        "subtotal": subtotal,
        "tax": tax,
        "discount": discount,
        "total": total,
        "watermark": watermark,
    }


def render_free_tool_document(template_slug, context, toolbar_html=""):
    html = render_template(document_template_path(context.get("document_type"), template_slug), **context)
    if toolbar_html:
        html = html.replace("</body>", f"{toolbar_html}</body>") if "</body>" in html else f"{html}{toolbar_html}"
    return html


def free_tool_document_number(document_type):
    prefix = "INV" if document_type == "invoice" else "QUO"
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def fetch_free_tool_documents(user_id, document_type=None, limit=None):
    conn = db()
    cur = conn.cursor()
    query = "SELECT * FROM free_tool_documents WHERE user_id=%s"
    params = [user_id]
    if document_type:
        query += " AND document_type=%s"
        params.append(document_type)
    query += " ORDER BY created_at DESC"
    if limit:
        query += " LIMIT %s"
        params.append(limit)
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_free_tool_document(document_id, user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM free_tool_documents WHERE id=%s AND user_id=%s LIMIT 1", (document_id, user_id))
    document = cur.fetchone()
    if not document:
        cur.close()
        conn.close()
        return None, []
    cur.execute("SELECT * FROM free_tool_document_items WHERE document_id=%s ORDER BY created_at ASC, id ASC", (document_id,))
    items = cur.fetchall()
    cur.close()
    conn.close()
    return document, items


def free_tool_counts(user_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS count FROM free_tool_documents WHERE user_id=%s AND document_type='invoice'", (user_id,))
    invoices = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) AS count FROM free_tool_documents WHERE user_id=%s AND document_type='quotation'", (user_id,))
    quotations = cur.fetchone()["count"]
    cur.close()
    conn.close()
    return invoices, quotations


def create_free_tool_document_record(cur, user, form_data, template_slug, document_type):
    items = compute_document_lines(form_data)
    subtotal, tax, discount, total = compute_document_totals(items, form_data.get("tax_percentage"), form_data.get("discount"))
    document_number = free_tool_document_number(document_type)
    watermark = user.get("plan_name", "free") == "free"
    cur.execute(
        """
        INSERT INTO free_tool_documents
        (user_id, template_slug, document_type, document_number, business_name, business_logo_url,
         business_email, business_phone, business_address, business_tax_number, payment_details,
         customer_name, customer_email, customer_phone, customer_address, notes, subtotal, tax,
         discount, total, watermark, status, due_date, valid_until, terms)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (
            user["id"],
            template_slug,
            document_type,
            document_number,
            user.get("business_name") or user.get("full_name") or "VibeHost Business",
            user.get("business_logo_url"),
            user.get("email"),
            user.get("business_phone"),
            user.get("business_address"),
            user.get("business_tax_number"),
            user.get("payment_details"),
            (form_data.get("customer_name") or "").strip(),
            (form_data.get("customer_email") or "").strip(),
            (form_data.get("customer_phone") or "").strip(),
            (form_data.get("customer_address") or "").strip(),
            (form_data.get("notes") or "").strip(),
            subtotal,
            tax,
            discount,
            total,
            watermark,
            "draft",
            form_data.get("due_date") if document_type == "invoice" else None,
            form_data.get("valid_until") if document_type == "quotation" else None,
            (form_data.get("terms") or "").strip(),
        ),
    )
    document_id = cur.fetchone()["id"]
    for item in items:
        cur.execute(
            """
            INSERT INTO free_tool_document_items
            (document_id, item_name, quantity, unit_price, total)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (document_id, item["item_name"], item["quantity"], item["unit_price"], item["total"]),
        )
    return document_id


def free_tool_document_pdf_response(user, document, items):
    if reportlab is None:
        html = render_template("free_tools/document_download_fallback.html", user=user, document=document, items=items)
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}
    pdf_bytes = generate_document_pdf(document, items, watermark_label="VibeHost Watermark" if document.get("watermark") else None)
    filename = f"{document.get('document_type','invoice')}-{document.get('document_number','document')}.pdf"
    return pdf_bytes, 200, {"Content-Type": "application/pdf", "Content-Disposition": f"inline; filename={filename}"}


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
    business["id"] = "preview-business"
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
            "homepage_text": "Explore a sample preview with dynamic business modules, enquiry capture and owner-managed content blocks.",
            "live_url": f"https://vibehost-demo.{BASE_DOMAIN}",
            "published": True,
        }
    )
    return business, site


def sample_site_items(slug):
    kind = template_slug(slug)
    if kind == "restaurant-food":
        return [
            {"name": "Chef Signature Burger", "description": "House burger with fries and sauce pairing.", "category": "Popular Meals", "price": Decimal("89"), "stock_quantity": 999, "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=900&q=80", "status": "active"},
            {"name": "Garden Bowl Plate", "description": "Fresh lunch option for office and delivery orders.", "category": "Light Meals", "price": Decimal("72"), "stock_quantity": 999, "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=900&q=80", "status": "active"},
            {"name": "Family Catering Tray", "description": "Large-format event tray for private catering requests.", "category": "Catering", "price": Decimal("299"), "stock_quantity": 999, "image_url": "https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=900&q=80", "status": "active"},
        ]
    if kind == "transport-shuttle":
        return [
            {"name": "Airport Shuttle", "description": "Pickup and dropoff route with luggage support.", "category": "Airport", "price": Decimal("350"), "stock_quantity": 12, "image_url": None, "status": "active"},
            {"name": "School Route", "description": "Morning and afternoon scheduled route service.", "category": "School", "price": Decimal("950"), "stock_quantity": 8, "image_url": None, "status": "active"},
            {"name": "Private Tour Transfer", "description": "Flexible charter option for tourism and events.", "category": "Tour", "price": Decimal("1200"), "stock_quantity": 5, "image_url": None, "status": "active"},
        ]
    if kind == "guesthouse-lodge":
        return [
            {"name": "Deluxe Room", "description": "Premium accommodation with breakfast and garden view.", "category": "Room", "price": Decimal("1450"), "stock_quantity": 4, "image_url": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=80", "status": "active"},
            {"name": "Family Chalet", "description": "Larger room layout for group or family stays.", "category": "Accommodation", "price": Decimal("2450"), "stock_quantity": 2, "image_url": "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=900&q=80", "status": "active"},
        ]
    if kind == "school-education":
        return [
            {"name": "Primary Program", "description": "Foundational classes with parent communication tools.", "category": "Programs", "price": Decimal("1800"), "stock_quantity": 60, "image_url": None, "status": "active"},
            {"name": "Secondary Stream", "description": "Exam-focused curriculum and progress tracking.", "category": "Classes", "price": Decimal("2400"), "stock_quantity": 40, "image_url": None, "status": "active"},
        ]
    return [
        {"name": "Premium Signature Offer", "description": "Owner-managed featured item displayed on the public website.", "category": "Featured", "price": Decimal("299"), "stock_quantity": 12, "image_url": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=900&q=80", "status": "active"},
        {"name": "Core Business Package", "description": "Service or package card powered by the owner dashboard.", "category": "Popular", "price": Decimal("450"), "stock_quantity": 8, "image_url": "https://images.unsplash.com/photo-1523381210434-271e8be1f52b?auto=format&fit=crop&w=900&q=80", "status": "active"},
        {"name": "Priority Support Option", "description": "A second dynamic item for preview and live business updates.", "category": "Priority", "price": Decimal("180"), "stock_quantity": 5, "image_url": "https://images.unsplash.com/photo-1483985988355-763728e1935b?auto=format&fit=crop&w=900&q=80", "status": "active"},
    ]


def sample_site_adverts():
    return [
        {"title": "Seasonal Highlight", "description": "Use owner-managed adverts for specials, promotions and launch campaigns.", "image_url": None, "button_text": "Open WhatsApp", "button_url": None, "status": "active"},
        {"title": "Customer Favourite", "description": "Showcase a second homepage callout without editing template code.", "image_url": None, "button_text": "Request Details", "button_url": None, "status": "active"},
    ]


def fetch_business_products(business_id, include_archived=False, limit=None):
    if not business_id:
        return []
    conn = db()
    cur = conn.cursor()
    query = "SELECT * FROM business_products WHERE business_id=%s"
    params = [business_id]
    if not include_archived:
        query += " AND status='active'"
    query += " ORDER BY created_at DESC"
    if limit:
        query += " LIMIT %s"
        params.append(limit)
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_business_adverts(business_id, limit=None):
    if not business_id:
        return []
    conn = db()
    cur = conn.cursor()
    query = "SELECT * FROM business_adverts WHERE business_id=%s AND status='active' ORDER BY created_at DESC"
    params = [business_id]
    if limit:
        query += " LIMIT %s"
        params.append(limit)
    try:
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
    except Exception:
        rows = []
    cur.close()
    conn.close()
    return rows


def render_site_template(slug, business, site, preview=False):
    template_path = TEMPLATE_MAP.get(template_slug(slug))
    if not template_path:
        abort(404)
    business = AttrDict(business or {})
    site = AttrDict(site or {})
    if site.get("font_style") and not site.get("font_family"):
        site["font_family"] = FONT_STYLE_MAP.get(site["font_style"], FONT_STYLE_MAP["modern"])
    managed_items = fetch_business_products(business.get("id"), include_archived=False, limit=6) if business.get("id") and not preview else []
    if not managed_items and preview:
        managed_items = sample_site_items(slug)
    adverts = fetch_business_adverts(business.get("id"), limit=3) if business.get("id") and not preview else []
    if not adverts and preview:
        adverts = sample_site_adverts()
    verification = fetch_business_verification(business.get("id")) if business.get("id") and not preview else AttrDict({"status": "approved"})
    customer_logged = bool(session.get("customer_id") and str(session.get("customer_business_id")) == str(business.get("id")))
    html = render_template(
        template_path,
        business=business,
        site=site,
        managed_items=managed_items,
        active_adverts=adverts,
        verification=verification,
        verification_approved=verification_approved(business, verification),
        preview_mode=preview,
        customer_logged_in=customer_logged,
        public_enquiry_endpoint=url_for("public_enquiry"),
        item_label=website_item_label(business.get("website_type") or slug).title(),
    )
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


def customer_logged_in():
    return bool(session.get("customer_id") and session.get("customer_business_id"))


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


def customer_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not customer_logged_in():
            return redirect(url_for("customer_login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def current_business_context(require_subdomain=False):
    subdomain = current_subdomain()
    if not subdomain:
        if session.get("customer_business_id"):
            conn = db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM business_profiles WHERE id=%s LIMIT 1", (session.get("customer_business_id"),))
            business = cur.fetchone()
            site = None
            if business:
                cur.execute("SELECT * FROM business_sites WHERE business_id=%s ORDER BY created_at ASC, id ASC LIMIT 1", (business["id"],))
                site = cur.fetchone()
            cur.close()
            conn.close()
            if business:
                return business, site
        if require_subdomain:
            return AttrDict({"business_name": "VibeHost Business", "subdomain": "", "whatsapp": "264812613261"}), AttrDict({})
        return None, None
    return fetch_business_site_by_subdomain(subdomain)


def get_owner_context():
    conn = db()
    cur = conn.cursor()
    owner_id = session.get("owner_id")
    business_id = session.get("business_id")
    
    if not owner_id or not business_id:
        # If master admin but no owner session, we shouldn't be here unless impersonating or something is wrong
        if master_logged_in():
            # Try to find a default business if we just navigated here? 
            # Usually impersonation sets owner_id.
            pass
        abort(403)

    cur.execute("SELECT * FROM business_owners WHERE id=%s LIMIT 1", (owner_id,))
    owner = cur.fetchone()
    cur.execute("SELECT * FROM business_profiles WHERE id=%s LIMIT 1", (business_id,))
    business = cur.fetchone()
    cur.execute("SELECT * FROM business_sites WHERE business_id=%s ORDER BY created_at ASC, id ASC LIMIT 1", (business_id,))
    site = cur.fetchone()
    cur.execute("SELECT * FROM subscriptions WHERE business_id=%s ORDER BY created_at DESC, id DESC LIMIT 1", (business_id,))
    subscription = cur.fetchone()
    cur.close()
    conn.close()
    if not owner or not business:
        if not master_logged_in():
            session.pop("owner_id", None)
            session.pop("business_id", None)
        abort(403)
    trial = trial_status_info(subscription)
    return owner, business, site, subscription, trial


def fetch_business_verification(business_id):
    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM business_verifications WHERE business_id=%s ORDER BY created_at DESC, id DESC LIMIT 1", (business_id,))
        verification = cur.fetchone()
    except Exception:
        verification = None
    cur.close()
    conn.close()
    return verification


def verification_status_value(business, verification=None):
    return (verification or {}).get("status") or (business or {}).get("verification_status") or "pending"


def verification_approved(business, verification=None):
    return verification_status_value(business, verification) == "approved"


def owner_sales_locked(trial, business, verification=None):
    if owner_write_blocked(trial):
        return True, "Your 14-day trial has ended. Upgrade to continue editing your website."
    if not verification_approved(business, verification):
        return True, "Business verification is required before selling or receiving customer orders."
    return False, None


def get_current_customer():
    customer_id = session.get("customer_id")
    business_id = session.get("customer_business_id")
    if not customer_id or not business_id:
        abort(403)
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customer_accounts WHERE id=%s AND business_id=%s LIMIT 1", (customer_id, business_id))
    customer = cur.fetchone()
    cur.execute("SELECT * FROM business_profiles WHERE id=%s LIMIT 1", (business_id,))
    business = cur.fetchone()
    cur.close()
    conn.close()
    if not customer or not business:
        session.pop("customer_id", None)
        session.pop("customer_business_id", None)
        abort(403)
    return customer, business


def get_free_tool_user():
    user_id = session.get("free_tool_user_id")
    if not user_id and master_logged_in():
        # Fallback for master view?
        abort(403)
        
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM free_tool_users WHERE id=%s LIMIT 1", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if not user:
        if not master_logged_in():
            session.pop("free_tool_user_id", None)
        abort(403)
    return user


def owner_write_blocked(trial):
    return trial["expired"]


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def record_stock_movement(cur, business_id, product_id, movement_type, quantity, note):
    cur.execute(
        """
        INSERT INTO stock_movements
        (business_id, product_id, movement_type, quantity, note)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (business_id, product_id, movement_type, quantity, (note or "").strip()),
    )


def owner_recent_activity(business_id, limit=8):
    conn = db()
    cur = conn.cursor()
    activities = []
    queries = [
        ("document", "SELECT id, document_number AS title, document_type AS detail, created_at FROM business_documents WHERE business_id=%s ORDER BY created_at DESC LIMIT %s"),
        ("order", "SELECT id, customer_name AS title, status AS detail, created_at FROM business_orders WHERE business_id=%s ORDER BY created_at DESC LIMIT %s"),
        ("stock", "SELECT id, movement_type AS title, note AS detail, created_at FROM stock_movements WHERE business_id=%s ORDER BY created_at DESC LIMIT %s"),
    ]
    for kind, query in queries:
        try:
            cur.execute(query, (business_id, limit))
            for row in cur.fetchall():
                activities.append(
                    {
                        "kind": kind,
                        "title": row.get("title") or row.get("id"),
                        "detail": row.get("detail") or "",
                        "created_at": row.get("created_at"),
                    }
                )
        except Exception:
            continue
    cur.close()
    conn.close()
    activities.sort(key=lambda row: row.get("created_at") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return activities[:limit]


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
    try:
        cur.execute("SELECT COUNT(*) AS count FROM business_products WHERE business_id=%s AND status='active' AND COALESCE(stock_quantity, 0) <= 3", (business_id,))
        low_stock = cur.fetchone()["count"]
        cur.execute("SELECT COUNT(*) AS count FROM business_staff WHERE business_id=%s", (business_id,))
        staff = cur.fetchone()["count"]
        cur.execute("SELECT COUNT(*) AS count FROM business_adverts WHERE business_id=%s AND status='active'", (business_id,))
        adverts = cur.fetchone()["count"]
        cur.execute(
            "SELECT COALESCE(SUM(total), 0) AS amount FROM business_documents WHERE business_id=%s AND document_type='invoice' AND created_at >= NOW() - INTERVAL '7 days'",
            (business_id,),
        )
        weekly_sales = cur.fetchone()["amount"]
        cur.execute(
            "SELECT COALESCE(SUM(total), 0) AS amount FROM business_documents WHERE business_id=%s AND document_type='invoice' AND created_at >= NOW() - INTERVAL '30 days'",
            (business_id,),
        )
        monthly_sales = cur.fetchone()["amount"]
    except Exception:
        low_stock = 0
        staff = 0
        adverts = 0
        weekly_sales = 0
        monthly_sales = 0
    cur.close()
    conn.close()
    return {
        "products": products,
        "orders": orders,
        "invoices": invoices,
        "quotations": quotations,
        "low_stock": low_stock,
        "staff": staff,
        "adverts": adverts,
        "weekly_sales": weekly_sales,
        "monthly_sales": monthly_sales,
    }


def owner_reports_data(business_id):
    stats = owner_dashboard_stats(business_id)
    conn = db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COALESCE(SUM(total_amount), 0) AS amount
            FROM business_orders
            WHERE business_id=%s AND created_at >= NOW() - INTERVAL '7 days' AND status IN ('paid', 'delivered', 'completed')
            """,
            (business_id,),
        )
        weekly_order_value = cur.fetchone()["amount"]
        cur.execute(
            """
            SELECT COALESCE(SUM(total_amount), 0) AS amount
            FROM business_orders
            WHERE business_id=%s AND created_at >= NOW() - INTERVAL '30 days' AND status IN ('paid', 'delivered', 'completed')
            """,
            (business_id,),
        )
        monthly_order_value = cur.fetchone()["amount"]
        cur.execute(
            "SELECT * FROM business_products WHERE business_id=%s AND status='active' AND COALESCE(stock_quantity, 0) <= 3 ORDER BY stock_quantity ASC, created_at DESC LIMIT 10",
            (business_id,),
        )
        low_stock_items = cur.fetchall()
    except Exception:
        weekly_order_value = 0
        monthly_order_value = 0
        low_stock_items = []
    cur.close()
    conn.close()
    return {
        "stats": stats,
        "weekly_total": Decimal(str(stats["weekly_sales"])) + Decimal(str(weekly_order_value)),
        "monthly_total": Decimal(str(stats["monthly_sales"])) + Decimal(str(monthly_order_value)),
        "recent_activity": owner_recent_activity(business_id),
        "low_stock_items": low_stock_items,
    }


def create_document(cur, business_id, document_type, form_data, business_data):
    items = compute_document_lines(form_data)
    subtotal, tax, discount, total = compute_document_totals(items, form_data.get("tax_percentage") or form_data.get("tax"), form_data.get("discount"))
    number_prefix = "INV" if document_type == "invoice" else "QUO"
    document_number = f"{number_prefix}-{slugify(str(uuid.uuid4())[:8]).upper()}"
    template_slug = (form_data.get("template_slug") or (business_data.get("selected_quotation_template") if document_type == "quotation" else business_data.get("selected_invoice_template")) or f"{document_type}_modern_clean")
    cur.execute(
        """
        INSERT INTO business_documents
        (business_id, document_type, document_number, customer_name, customer_email,
         customer_phone, customer_address, notes, subtotal, tax, discount, total, status,
         business_name, business_logo_url, business_email, business_phone, business_address,
         business_tax_number, payment_details, due_date, valid_until, terms, template_slug, watermark)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (
            business_id,
            document_type,
            document_number,
            (form_data.get("customer_name") or "").strip(),
            (form_data.get("customer_email") or "").strip(),
            (form_data.get("customer_phone") or "").strip(),
            (form_data.get("customer_address") or "").strip(),
            (form_data.get("notes") or "").strip(),
            subtotal,
            tax,
            discount,
            total,
            (form_data.get("status") or "draft").strip() or "draft",
            business_data.get("business_name"),
            business_data.get("business_logo_url"),
            business_data.get("business_email"),
            business_data.get("business_phone"),
            business_data.get("business_address"),
            business_data.get("business_tax_number"),
            business_data.get("payment_details"),
            form_data.get("due_date") if document_type == "invoice" else None,
            form_data.get("valid_until") if document_type == "quotation" else None,
            (form_data.get("terms") or "").strip(),
            template_slug,
            business_data.get("watermark", True),
        ),
    )
    document_id = cur.fetchone()["id"]
    for item in items:
        cur.execute(
            """
            INSERT INTO business_document_items
            (document_id, item_name, quantity, unit_price, total)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (document_id, item["item_name"], item["quantity"], item["unit_price"], item["total"]),
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
    if reportlab is None:
        html = render_template("owner/document_download_fallback.html", business=business, document=document, items=items)
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}
    document = dict(document)
    document.setdefault("business_name", business.get("business_name"))
    document.setdefault("business_logo_url", document.get("business_logo_url") or business.get("logo_url"))
    watermark_label = "VibeHost Trial" if document.get("watermark") else None
    pdf_bytes = generate_document_pdf(document, items, watermark_label=watermark_label)
    return pdf_bytes, 200, {
        "Content-Type": "application/pdf",
        "Content-Disposition": f"inline; filename={document['document_type']}-{document['document_number']}.pdf",
    }


def get_system_setting(key, default=None):
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT value FROM system_settings WHERE key=%s LIMIT 1", (key,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return row["value"]
    except Exception:
        pass
    return default


@app.context_processor
def inject_system_settings():
    return dict(
        whatsapp_number=get_system_setting("whatsapp_number", "+264812613261"),
        support_email=get_system_setting("support_email", "support@vibehost.com"),
        maintenance_message=get_system_setting("maintenance_message", ""),
    )


@app.before_request
def maybe_serve_subdomain_site():
    subdomain = current_subdomain()
    if not subdomain:
        return None
    if request.path == "/favicon.ico":
        return None
    if any(request.path.startswith(prefix) for prefix in SUBDOMAIN_APP_PREFIXES):
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
                         subdomain, region, town, website_type, description, verification_status, is_public_active)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',false)
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
                        (business_id, owner_name, email, password_hash, role, phone)
                        VALUES (%s,%s,%s,%s,%s,%s)
                        RETURNING id
                        """,
                        (business_id, owner_name or business_name, owner_email, generate_password_hash(owner_password), "owner", phone),
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
                    return redirect(url_for("owner_onboarding"))
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
        
        # 1. Check Master Admin
        cur.execute("SELECT * FROM master_admins WHERE email=%s AND is_active=TRUE LIMIT 1", (email,))
        master = cur.fetchone()
        if master and check_password_hash(master["password_hash"], password):
            session.clear()
            session["master_admin_id"] = str(master["id"])
            session["master_name"] = master["full_name"]
            cur.close()
            conn.close()
            return redirect(url_for("master_dashboard"))
            
        # 2. Check Business Owner
        cur.execute("SELECT * FROM business_owners WHERE email=%s LIMIT 1", (email,))
        owner = cur.fetchone()
        if owner and check_password_hash(owner["password_hash"], password):
            cur.execute("SELECT verification_status FROM business_profiles WHERE id=%s LIMIT 1", (owner["business_id"],))
            business_row = cur.fetchone()
            session.clear()
            session["owner_id"] = str(owner["id"])
            session["business_id"] = str(owner["business_id"])
            cur.close()
            conn.close()
            if (business_row or {}).get("verification_status") == "approved":
                return redirect(request.args.get("next") or url_for("owner_dashboard"))
            return redirect(url_for("owner_verification_status"))
            
        # 3. Check Free Tool User
        cur.execute("SELECT * FROM free_tool_users WHERE email=%s LIMIT 1", (email,))
        free_user = cur.fetchone()
        if free_user and check_password_hash(free_user["password_hash"], password):
            session.clear()
            session["free_tool_user_id"] = str(free_user["id"])
            cur.close()
            conn.close()
            return redirect(url_for("free_tools_dashboard"))

        cur.close()
        conn.close()
        error = "Invalid email or password."
    return render_template("owner/login.html", error=error, support_phone=SUPPORT_PHONE, support_whatsapp_url=SUPPORT_WHATSAPP_URL)


@app.route("/owner/logout")
def owner_logout():
    session.clear()
    return redirect(url_for("owner_login"))


@app.route("/master/dashboard")
@master_required
def master_dashboard():
    conn = db()
    cur = conn.cursor()
    
    # Stats
    cur.execute("SELECT COUNT(*) AS count FROM business_profiles")
    total_websites = cur.fetchone()["count"]
    
    cur.execute("SELECT COUNT(*) AS count FROM subscriptions WHERE status='trial' AND trial_expires_at > NOW()")
    active_trials = cur.fetchone()["count"]
    
    cur.execute("SELECT COUNT(*) AS count FROM subscriptions WHERE status='trial' AND trial_expires_at <= NOW()")
    expired_trials = cur.fetchone()["count"]
    
    cur.execute("SELECT COUNT(*) AS count FROM subscriptions WHERE status='active'")
    paid_websites = cur.fetchone()["count"]
    
    cur.execute("SELECT COUNT(*) AS count FROM business_owners")
    website_owners = cur.fetchone()["count"]

    try:
        cur.execute("SELECT COUNT(*) AS count FROM customer_accounts")
        customer_accounts_count = cur.fetchone()["count"]
    except Exception:
        customer_accounts_count = 0

    cur.execute("SELECT COUNT(*) AS count FROM business_profiles WHERE verification_status='approved'")
    verified_businesses = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) AS count FROM business_profiles WHERE verification_status='pending'")
    pending_verifications = cur.fetchone()["count"]
    cur.execute("SELECT COUNT(*) AS count FROM business_profiles WHERE verification_status='rejected'")
    rejected_verifications = cur.fetchone()["count"]
    
    cur.execute("SELECT COUNT(*) AS count FROM free_tool_users")
    free_tool_users_count = cur.fetchone()["count"]
    
    cur.execute("SELECT COUNT(*) AS count FROM business_documents WHERE document_type='invoice'")
    invoices_count = cur.fetchone()["count"]
    
    cur.execute("SELECT COUNT(*) AS count FROM business_documents WHERE document_type='quotation'")
    quotations_count = cur.fetchone()["count"]
    
    cur.execute("SELECT COUNT(*) AS count FROM free_tool_documents")
    free_docs_count = cur.fetchone()["count"]
    
    total_documents = invoices_count + quotations_count + free_docs_count
    
    cur.execute("SELECT b.*, s.status, s.trial_expires_at FROM business_profiles b LEFT JOIN subscriptions s ON b.id = s.business_id ORDER BY b.created_at DESC LIMIT 5")
    recent_websites = cur.fetchall()
    
    cur.execute("SELECT * FROM business_documents ORDER BY created_at DESC LIMIT 5")
    recent_documents = cur.fetchall()
    
    cur.execute("SELECT b.business_name, s.trial_expires_at FROM business_profiles b JOIN subscriptions s ON b.id = s.business_id WHERE s.status='trial' AND s.trial_expires_at BETWEEN NOW() AND NOW() + interval '3 days' ORDER BY s.trial_expires_at ASC")
    trial_expiry_alerts = cur.fetchall()

    try:
        cur.execute(
            """
            SELECT v.*, b.business_name, o.email AS owner_email
            FROM business_verifications v
            JOIN business_profiles b ON b.id = v.business_id
            LEFT JOIN business_owners o ON o.id = v.owner_id
            ORDER BY v.created_at DESC
            LIMIT 5
            """
        )
        recent_verifications = cur.fetchall()
    except Exception:
        recent_verifications = []
    
    cur.close()
    conn.close()
    
    return render_template(
        "master/dashboard.html",
        total_websites=total_websites,
        active_trials=active_trials,
        expired_trials=expired_trials,
        paid_websites=paid_websites,
        website_owners=website_owners,
        customer_accounts_count=customer_accounts_count,
        free_tool_users=free_tool_users_count,
        verified_businesses=verified_businesses,
        pending_verifications=pending_verifications,
        rejected_verifications=rejected_verifications,
        invoices_count=invoices_count,
        quotations_count=quotations_count,
        total_documents=total_documents,
        recent_websites=recent_websites,
        recent_documents=recent_documents,
        trial_expiry_alerts=trial_expiry_alerts
        ,
        recent_verifications=recent_verifications,
    )


@app.route("/master/websites")
@master_required
def master_websites():
    search = request.args.get("q", "").strip()
    conn = db()
    cur = conn.cursor()
    query = """
        SELECT b.*, o.email as owner_email, s.plan_name, s.status as sub_status, s.trial_expires_at 
        FROM business_profiles b 
        LEFT JOIN business_owners o ON b.id = o.business_id 
        LEFT JOIN (
            SELECT DISTINCT ON (business_id) * FROM subscriptions ORDER BY business_id, created_at DESC
        ) s ON b.id = s.business_id
    """
    params = []
    if search:
        query += " WHERE b.business_name ILIKE %s OR o.email ILIKE %s OR b.subdomain ILIKE %s"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    
    query += " ORDER BY b.created_at DESC"
    cur.execute(query, tuple(params))
    websites = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("master/websites.html", websites=websites, search=search)


@app.route("/master/websites/<business_id>")
@master_required
def master_website_detail(business_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT b.*, s.plan_name, s.status as sub_status, s.trial_started_at, s.trial_expires_at FROM business_profiles b LEFT JOIN (SELECT DISTINCT ON (business_id) * FROM subscriptions ORDER BY business_id, created_at DESC) s ON b.id = s.business_id WHERE b.id=%s LIMIT 1", (business_id,))
    business = cur.fetchone()
    if not business:
        cur.close()
        conn.close()
        abort(404)
        
    cur.execute("SELECT * FROM business_owners WHERE business_id=%s LIMIT 1", (business_id,))
    owner = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) AS count FROM business_products WHERE business_id=%s", (business_id,))
    products_count = cur.fetchone()["count"]
    
    cur.execute("SELECT COUNT(*) AS count FROM business_orders WHERE business_id=%s", (business_id,))
    orders_count = cur.fetchone()["count"]
    
    cur.execute("SELECT COUNT(*) AS count FROM business_documents WHERE business_id=%s AND document_type='invoice'", (business_id,))
    invoices_count = cur.fetchone()["count"]
    
    cur.execute("SELECT COUNT(*) AS count FROM business_documents WHERE business_id=%s AND document_type='quotation'", (business_id,))
    quotations_count = cur.fetchone()["count"]
    try:
        cur.execute("SELECT COUNT(*) AS count FROM customer_accounts WHERE business_id=%s", (business_id,))
        customers_count = cur.fetchone()["count"]
        cur.execute("SELECT * FROM business_verifications WHERE business_id=%s ORDER BY created_at DESC LIMIT 1", (business_id,))
        verification = cur.fetchone()
    except Exception:
        customers_count = 0
        verification = None
    
    cur.close()
    conn.close()
    
    return render_template(
        "master/website_detail.html",
        business=business,
        owner=owner,
        products_count=products_count,
        orders_count=orders_count,
        customers_count=customers_count,
        verification=verification,
        invoices_count=invoices_count,
        quotations_count=quotations_count
    )


@app.route("/master/websites/<business_id>/status", methods=["POST"])
@master_required
def master_website_status(business_id):
    status = request.form.get("status")
    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE subscriptions SET status=%s, updated_at=NOW() WHERE business_id=%s", (status, business_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("master_website_detail", business_id=business_id))


@app.route("/master/websites/<business_id>/plan", methods=["POST"])
@master_required
def master_website_plan(business_id):
    plan = request.form.get("plan")
    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE subscriptions SET plan_name=%s, updated_at=NOW() WHERE business_id=%s", (plan, business_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("master_website_detail", business_id=business_id))


@app.route("/master/websites/<business_id>/trial-extend", methods=["POST"])
@master_required
def master_website_trial_extend(business_id):
    days = int(request.form.get("days", 7))
    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE subscriptions SET trial_expires_at = trial_expires_at + interval '%s days', updated_at=NOW() WHERE business_id=%s", (days, business_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("master_website_detail", business_id=business_id))


@app.route("/master/owners")
@master_required
def master_owners():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT o.*, b.business_name FROM business_owners o LEFT JOIN business_profiles b ON o.business_id = b.id ORDER BY o.created_at DESC")
    owners = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("master/owners.html", owners=owners)


@app.route("/master/free-tool-users")
@master_required
def master_free_tool_users():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM free_tool_users ORDER BY created_at DESC")
    users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("master/free_tool_users.html", users=users)


@app.route("/master/documents")
@master_required
def master_documents():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_documents ORDER BY created_at DESC LIMIT 50")
    business_docs = cur.fetchall()
    cur.execute("SELECT * FROM free_tool_documents ORDER BY created_at DESC LIMIT 50")
    free_docs = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("master/documents.html", business_docs=business_docs, free_docs=free_docs)


@app.route("/master/verifications")
@master_required
def master_verifications():
    conn = db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT v.*, b.business_name, b.subdomain, b.verification_status, o.owner_name, o.email AS owner_email,
                   (SELECT COUNT(*) FROM customer_accounts c WHERE c.business_id = b.id) AS customer_count
            FROM business_verifications v
            JOIN business_profiles b ON b.id = v.business_id
            LEFT JOIN business_owners o ON o.id = v.owner_id
            ORDER BY CASE v.status WHEN 'pending' THEN 0 WHEN 'rejected' THEN 1 ELSE 2 END, v.created_at DESC
            """
        )
        verifications = cur.fetchall()
    except Exception:
        verifications = []
    cur.close()
    conn.close()
    return render_template("master/verifications.html", verifications=verifications)


@app.route("/master/verifications/<verification_id>")
@master_required
def master_verification_detail(verification_id):
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT v.*, b.business_name, b.subdomain, b.email AS business_email, b.phone AS business_phone,
               b.whatsapp, b.town, b.region, b.verification_status, o.owner_name, o.email AS owner_email, o.phone AS owner_phone
        FROM business_verifications v
        JOIN business_profiles b ON b.id = v.business_id
        LEFT JOIN business_owners o ON o.id = v.owner_id
        WHERE v.id=%s
        LIMIT 1
        """,
        (verification_id,),
    )
    verification = cur.fetchone()
    if not verification:
        cur.close()
        conn.close()
        abort(404)
    try:
        cur.execute("SELECT COUNT(*) AS count FROM customer_accounts WHERE business_id=%s", (verification["business_id"],))
        customer_count = cur.fetchone()["count"]
    except Exception:
        customer_count = 0
    cur.close()
    conn.close()
    return render_template("master/verification_detail.html", verification=verification, customer_count=customer_count)


@app.route("/master/verifications/<verification_id>/file/<doc_type>")
@master_required
def master_verification_file(verification_id, doc_type):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_verifications WHERE id=%s LIMIT 1", (verification_id,))
    verification = cur.fetchone()
    cur.close()
    conn.close()
    if not verification:
        abort(404)
    field_map = {
        "business_registration": "business_registration_url",
        "owner_id": "owner_id_url",
        "proof_of_address": "proof_of_address_url",
    }
    upload_url = verification.get(field_map.get(doc_type, ""))
    file_path = uploaded_file_path(upload_url)
    if not file_path:
        abort(404)
    return send_file(file_path)


@app.route("/master/verifications/<verification_id>/approve", methods=["POST"])
@master_required
def master_verification_approve(verification_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_verifications WHERE id=%s LIMIT 1", (verification_id,))
    verification = cur.fetchone()
    if not verification:
        cur.close()
        conn.close()
        abort(404)
    cur.execute(
        """
        UPDATE business_verifications
        SET status='approved', admin_notes=%s, reviewed_by=%s, reviewed_at=NOW()
        WHERE id=%s
        """,
        ((request.form.get("admin_notes") or "").strip(), session.get("master_admin_id"), verification_id),
    )
    cur.execute("UPDATE business_profiles SET verification_status='approved', is_public_active=true WHERE id=%s", (verification["business_id"],))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("master_verification_detail", verification_id=verification_id))


@app.route("/master/verifications/<verification_id>/reject", methods=["POST"])
@master_required
def master_verification_reject(verification_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_verifications WHERE id=%s LIMIT 1", (verification_id,))
    verification = cur.fetchone()
    if not verification:
        cur.close()
        conn.close()
        abort(404)
    cur.execute(
        """
        UPDATE business_verifications
        SET status='rejected', admin_notes=%s, reviewed_by=%s, reviewed_at=NOW()
        WHERE id=%s
        """,
        ((request.form.get("admin_notes") or "").strip(), session.get("master_admin_id"), verification_id),
    )
    cur.execute("UPDATE business_profiles SET verification_status='rejected', is_public_active=false WHERE id=%s", (verification["business_id"],))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("master_verification_detail", verification_id=verification_id))


@app.route("/master/payments")
@master_required
def master_payments():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT p.*, b.business_name, u.full_name as user_name FROM payments p LEFT JOIN business_profiles b ON p.business_id = b.id LEFT JOIN free_tool_users u ON p.free_tool_user_id = u.id ORDER BY p.created_at DESC")
    payments = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("master/payments.html", payments=payments)


@app.route("/master/templates")
@master_required
def master_templates_list():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM website_templates ORDER BY name")
    website_templates = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("master/templates.html", website_templates=website_templates, doc_templates=DOCUMENT_TEMPLATE_ROWS)


@app.route("/master/settings", methods=["GET", "POST"])
@master_required
def master_settings():
    conn = db()
    cur = conn.cursor()
    if request.method == "POST":
        for key, value in request.form.items():
            cur.execute("INSERT INTO system_settings (key, value, updated_at) VALUES (%s, %s, NOW()) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()", (key, value))
        conn.commit()
        
    cur.execute("SELECT * FROM system_settings")
    settings = {row["key"]: row["value"] for row in cur.fetchall()}
    cur.close()
    conn.close()
    return render_template("master/settings.html", settings=settings)


@app.route("/master/system-health")
@master_required
def master_system_health():
    health = {
        "neon_connected": False,
        "supabase_connected": False,
        "uploads_writable": os.access(UPLOAD_FOLDER, os.W_OK),
        "template_count": len(TEMPLATE_ROWS),
        "pdf_service": reportlab is not None
    }
    try:
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        health["neon_connected"] = True
        cur.close()
        conn.close()
    except Exception:
        pass
        
    if supabase_client():
        health["supabase_connected"] = True
        
    return render_template("master/system_health.html", health=health)


@app.route("/master/impersonate-owner/<owner_id>", methods=["POST"])
@master_required
def master_impersonate_owner(owner_id):
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_owners WHERE id=%s LIMIT 1", (owner_id,))
    owner = cur.fetchone()
    cur.close()
    conn.close()
    if owner:
        session["original_master_id"] = session["master_admin_id"]
        session["owner_id"] = str(owner["id"])
        session["business_id"] = str(owner["business_id"])
        return redirect(url_for("owner_dashboard"))
    return redirect(url_for("master_owners"))


@app.route("/master/stop-impersonation", methods=["POST"])
def master_stop_impersonation():
    if session.get("original_master_id"):
        session["master_admin_id"] = session["original_master_id"]
        session.pop("original_master_id", None)
        session.pop("owner_id", None)
        session.pop("business_id", None)
        return redirect(url_for("master_dashboard"))
    return redirect(url_for("owner_dashboard"))


@app.route("/owner/onboarding")
@owner_required
def owner_onboarding():
    return redirect(url_for("owner_verification_status"))


@app.route("/owner/verification", methods=["GET", "POST"])
@owner_required
def owner_verification():
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    error = None
    success = None
    if request.method == "POST":
        registration_url = upload_logo(request.files.get("business_registration"), subdir=f"verifications/{business['id']}", allowed_extensions=ALLOWED_VERIFICATION_EXTENSIONS)
        owner_id_url = upload_logo(request.files.get("owner_id_document"), subdir=f"verifications/{business['id']}", allowed_extensions=ALLOWED_VERIFICATION_EXTENSIONS)
        proof_of_address_url = upload_logo(request.files.get("proof_of_address"), subdir=f"verifications/{business['id']}", allowed_extensions=ALLOWED_VERIFICATION_EXTENSIONS)
        if not (registration_url and owner_id_url and proof_of_address_url):
            error = "Please upload all three verification files as PDF, PNG, JPG or JPEG."
        else:
            conn = db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO business_verifications
                (business_id, owner_id, business_registration_url, owner_id_url, proof_of_address_url, status, admin_notes)
                VALUES (%s,%s,%s,%s,%s,'pending','')
                RETURNING id
                """,
                (business["id"], owner["id"], registration_url, owner_id_url, proof_of_address_url),
            )
            cur.execute("UPDATE business_profiles SET verification_status='pending', is_public_active=false WHERE id=%s", (business["id"],))
            conn.commit()
            cur.close()
            conn.close()
            success = "Verification documents uploaded successfully. A master admin will review them."
            verification = fetch_business_verification(business["id"]) or {}
    return render_template("owner/verification.html", owner=owner, business=business, site=site, trial=trial, verification=verification, error=error, success=success)


@app.route("/owner/verification/status")
@owner_required
def owner_verification_status():
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    return render_template("owner/verification_status.html", owner=owner, business=business, site=site, trial=trial, verification=verification)


@app.route("/owner/verification/file/<doc_type>")
@owner_required
def owner_verification_file(doc_type):
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    field_map = {
        "business_registration": "business_registration_url",
        "owner_id": "owner_id_url",
        "proof_of_address": "proof_of_address_url",
    }
    upload_url = verification.get(field_map.get(doc_type, ""))
    file_path = uploaded_file_path(upload_url)
    if not file_path:
        abort(404)
    return send_file(file_path)


@app.route("/owner/dashboard")
@owner_required
def owner_dashboard():
    owner, business, site, subscription, trial = get_owner_context()
    stats = owner_dashboard_stats(business["id"])
    reports = owner_reports_data(business["id"])
    verification = fetch_business_verification(business["id"]) or {}
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM business_documents WHERE business_id=%s ORDER BY created_at DESC LIMIT 6",
        (business["id"],),
    )
    recent_documents = cur.fetchall()
    try:
        cur.execute("SELECT * FROM business_orders WHERE business_id=%s ORDER BY created_at DESC LIMIT 5", (business["id"],))
        recent_orders = cur.fetchall()
    except Exception:
        recent_orders = []
    cur.close()
    conn.close()
    return render_template(
        "owner/dashboard.html",
        owner=owner,
        business=business,
        site=site,
        subscription=subscription,
        trial=trial,
        verification=verification,
        stats=stats,
        reports=reports,
        recent_documents=recent_documents,
        recent_orders=recent_orders,
        owner_document_limit=OWNER_DOCUMENT_LIMIT,
        item_label=website_item_label(business.get("website_type")).title(),
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/owner/site-editor", methods=["GET", "POST"])
@owner_required
def owner_site_editor():
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
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
                    hero_subtitle=%s, homepage_text=%s, font_style=%s, wallpaper_style=%s
                WHERE business_id=%s
                """,
                (
                    request.form.get("primary_color") or site.get("primary_color"),
                    request.form.get("secondary_color") or site.get("secondary_color"),
                    request.form.get("accent_color") or site.get("accent_color"),
                    (request.form.get("hero_title") or "").strip(),
                    (request.form.get("hero_subtitle") or "").strip(),
                    (request.form.get("homepage_text") or "").strip(),
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
        verification=verification,
        error=error,
        success=success,
        item_label=website_item_label(business.get("website_type")).title(),
        region_options=REGION_OPTIONS,
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/owner/products", methods=["GET", "POST"])
@owner_required
def owner_products():
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    error = None
    success = None
    if request.method == "POST":
        locked, lock_message = owner_sales_locked(trial, business, verification)
        if locked:
            error = lock_message
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
                    RETURNING id
                    """,
                    (
                        business["id"],
                        (request.form.get("name") or "").strip(),
                        (request.form.get("description") or "").strip(),
                        (request.form.get("category") or "").strip(),
                        decimal_value(request.form.get("price"), "0"),
                        image_url,
                        int(request.form.get("stock_quantity") or 0),
                        (request.form.get("status") or "active").strip() or "active",
                    ),
                )
                product_id = cur.fetchone()["id"]
                if product_id and safe_int(request.form.get("stock_quantity"), 0) > 0:
                    record_stock_movement(cur, business["id"], product_id, "stock_in", safe_int(request.form.get("stock_quantity"), 0), "Initial product stock")
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
        verification=verification,
        products=products,
        item_label=website_item_label(business.get("website_type")),
        error=error,
        success=success,
    )


@app.route("/owner/products/<product_id>/delete", methods=["POST"])
@owner_required
def owner_product_delete(product_id):
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    locked, _ = owner_sales_locked(trial, business, verification)
    if not locked:
        conn = db()
        cur = conn.cursor()
        cur.execute("UPDATE business_products SET status='archived' WHERE id=%s AND business_id=%s", (product_id, business["id"]))
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for("owner_products"))


@app.route("/owner/products/<product_id>/stock", methods=["POST"])
@owner_required
def owner_product_stock(product_id):
    return owner_stock_adjust(product_id)


@app.route("/owner/orders")
@owner_required
def owner_orders():
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_orders WHERE business_id=%s ORDER BY created_at DESC", (business["id"],))
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("owner/orders.html", owner=owner, business=business, trial=trial, orders=orders, verification=verification)


@app.route("/owner/orders/<order_id>/status", methods=["POST"])
@owner_required
def owner_order_status(order_id):
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    locked, _ = owner_sales_locked(trial, business, verification)
    if not locked:
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
    payload_json = request.get_json(silent=True) or {}
    business_id = request.form.get("business_id") or payload_json.get("business_id")
    if not business_id:
        return jsonify({"ok": False, "error": "business_id is required"}), 400
    payload = request.form if request.form else payload_json
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_profiles WHERE id=%s LIMIT 1", (business_id,))
    business = cur.fetchone()
    if not business or (business.get("verification_status") or "pending") != "approved":
        cur.close()
        conn.close()
        return jsonify({"ok": False, "error": "This business is still being verified. Please contact the business directly."}), 403
    customer_id = None
    if session.get("customer_id") and str(session.get("customer_business_id")) == str(business_id):
        customer_id = session.get("customer_id")
    cur.execute(
        """
        INSERT INTO business_orders
        (business_id, customer_id, customer_name, customer_email, customer_phone, order_type, message, status, total_amount, source,
         delivery_method, delivery_address, delivery_time, assigned_staff, delivery_status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,'new',%s,'website',%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (
            business_id,
            customer_id,
            (payload.get("customer_name") or "").strip(),
            (payload.get("customer_email") or "").strip(),
            (payload.get("customer_phone") or "").strip(),
            (payload.get("order_type") or "enquiry").strip(),
            (payload.get("message") or "").strip(),
            decimal_value(payload.get("total_amount"), "0"),
            (payload.get("delivery_method") or "").strip(),
            (payload.get("delivery_address") or "").strip(),
            (payload.get("delivery_time") or "").strip(),
            (payload.get("assigned_staff") or "").strip(),
            (payload.get("delivery_status") or "pending").strip() or "pending",
        ),
    )
    order_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True, "order_id": str(order_id)})


@app.route("/owner/stock")
@owner_required
def owner_stock():
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    conn = db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM business_products WHERE business_id=%s ORDER BY COALESCE(stock_quantity, 0) ASC, created_at DESC",
        (business["id"],),
    )
    products = cur.fetchall()
    try:
        cur.execute(
            """
            SELECT m.*, p.name AS product_name
            FROM stock_movements m
            LEFT JOIN business_products p ON p.id = m.product_id
            WHERE m.business_id=%s
            ORDER BY m.created_at DESC
            LIMIT 50
            """,
            (business["id"],),
        )
        movements = cur.fetchall()
    except Exception:
        movements = []
    cur.close()
    conn.close()
    return render_template("owner/stock.html", owner=owner, business=business, trial=trial, products=products, movements=movements, verification=verification)


@app.route("/owner/stock/<product_id>/adjust", methods=["POST"])
@owner_required
def owner_stock_adjust(product_id):
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    locked, _ = owner_sales_locked(trial, business, verification)
    if locked:
        return redirect(url_for("owner_stock"))
    movement_type = (request.form.get("movement_type") or "adjustment").strip() or "adjustment"
    quantity = safe_int(request.form.get("quantity"), 0)
    note = request.form.get("note") or ""
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_products WHERE id=%s AND business_id=%s LIMIT 1", (product_id, business["id"]))
    product = cur.fetchone()
    if product:
        signed_quantity = quantity
        if movement_type in {"stock_out", "sale"}:
            signed_quantity = -abs(quantity)
        elif movement_type in {"stock_in", "return"}:
            signed_quantity = abs(quantity)
        cur.execute(
            "UPDATE business_products SET stock_quantity=COALESCE(stock_quantity, 0) + %s WHERE id=%s AND business_id=%s",
            (signed_quantity, product_id, business["id"]),
        )
        record_stock_movement(cur, business["id"], product_id, movement_type, signed_quantity, note)
        conn.commit()
    cur.close()
    conn.close()
    return redirect(request.referrer or url_for("owner_stock"))


@app.route("/owner/delivery")
@owner_required
def owner_delivery():
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM business_orders
        WHERE business_id=%s
        ORDER BY created_at DESC
        """,
        (business["id"],),
    )
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("owner/delivery.html", owner=owner, business=business, trial=trial, orders=orders, verification=verification)


@app.route("/owner/delivery/<order_id>/update", methods=["POST"])
@owner_required
def owner_delivery_update(order_id):
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    locked, _ = owner_sales_locked(trial, business, verification)
    if not locked:
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE business_orders
            SET delivery_method=%s, delivery_address=%s, delivery_time=%s, assigned_staff=%s, delivery_status=%s
            WHERE id=%s AND business_id=%s
            """,
            (
                (request.form.get("delivery_method") or "").strip(),
                (request.form.get("delivery_address") or "").strip(),
                (request.form.get("delivery_time") or "").strip(),
                (request.form.get("assigned_staff") or "").strip(),
                (request.form.get("delivery_status") or "pending").strip() or "pending",
                order_id,
                business["id"],
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for("owner_delivery"))


@app.route("/owner/staff", methods=["GET", "POST"])
@owner_required
def owner_staff():
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    error = None
    success = None
    if request.method == "POST":
        locked, lock_message = owner_sales_locked(trial, business, verification)
        if locked:
            error = lock_message
        else:
            conn = db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO business_staff
                (business_id, full_name, email, phone, role, status)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (
                    business["id"],
                    (request.form.get("full_name") or "").strip(),
                    (request.form.get("email") or "").strip(),
                    (request.form.get("phone") or "").strip(),
                    (request.form.get("role") or "support").strip() or "support",
                    (request.form.get("status") or "active").strip() or "active",
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
            success = "Staff member added."
    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM business_staff WHERE business_id=%s ORDER BY created_at DESC", (business["id"],))
        staff_rows = cur.fetchall()
    except Exception:
        staff_rows = []
    cur.close()
    conn.close()
    return render_template("owner/staff.html", owner=owner, business=business, trial=trial, staff_rows=staff_rows, error=error, success=success, verification=verification)


@app.route("/owner/staff/<staff_id>/delete", methods=["POST"])
@owner_required
def owner_staff_delete(staff_id):
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    locked, _ = owner_sales_locked(trial, business, verification)
    if not locked:
        conn = db()
        cur = conn.cursor()
        cur.execute("DELETE FROM business_staff WHERE id=%s AND business_id=%s", (staff_id, business["id"]))
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for("owner_staff"))


@app.route("/owner/marketing", methods=["GET", "POST"])
@owner_required
def owner_marketing():
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    error = None
    success = None
    if request.method == "POST":
        locked, lock_message = owner_sales_locked(trial, business, verification)
        if locked:
            error = lock_message
        else:
            image_url = upload_logo(request.files.get("image"))
            conn = db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO business_adverts
                (business_id, title, description, image_url, button_text, button_url, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    business["id"],
                    (request.form.get("title") or "").strip(),
                    (request.form.get("description") or "").strip(),
                    image_url,
                    (request.form.get("button_text") or "Learn More").strip(),
                    (request.form.get("button_url") or "").strip(),
                    (request.form.get("status") or "active").strip() or "active",
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
            success = "Homepage advert saved."
    conn = db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM business_adverts WHERE business_id=%s ORDER BY created_at DESC", (business["id"],))
        adverts = cur.fetchall()
    except Exception:
        adverts = []
    cur.close()
    conn.close()
    return render_template("owner/marketing.html", owner=owner, business=business, trial=trial, adverts=adverts, error=error, success=success, verification=verification)


@app.route("/owner/reports")
@owner_required
def owner_reports():
    owner, business, site, subscription, trial = get_owner_context()
    reports = owner_reports_data(business["id"])
    verification = fetch_business_verification(business["id"]) or {}
    return render_template("owner/reports.html", owner=owner, business=business, trial=trial, reports=reports, verification=verification)


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
    verification = fetch_business_verification(business["id"]) or {}
    error = None
    success = None
    business_data = {
        "business_name": business.get("business_name"),
        "business_logo_url": business.get("logo_url"),
        "business_email": business.get("email"),
        "business_phone": business.get("phone"),
        "business_address": ", ".join([part for part in [business.get("town"), business.get("region")] if part]),
        "business_tax_number": business.get("business_tax_number"),
        "payment_details": business.get("payment_details"),
        "selected_invoice_template": business.get("selected_invoice_template") or "invoice_modern_clean",
        "selected_quotation_template": business.get("selected_quotation_template") or "quotation_modern_clean",
        "watermark": subscription and subscription.get("status") == "trial",
    }
    if request.method == "POST":
        locked, lock_message = owner_sales_locked(trial, business, verification)
        if locked:
            error = lock_message
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
                create_document(cur, business["id"], document_type, request.form, business_data)
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
        site=site,
        subscription=subscription,
        trial=trial,
        verification=verification,
        documents=documents,
        document_type=document_type,
        error=error,
        success=success,
        template_slug=business_data.get("selected_quotation_template") if document_type == "quotation" else business_data.get("selected_invoice_template"),
    )


@app.route("/owner/invoices/create", methods=["GET", "POST"])
@owner_required
def owner_invoices_create():
    return owner_documents("invoice")


@app.route("/owner/quotations/create", methods=["GET", "POST"])
@owner_required
def owner_quotations_create():
    return owner_documents("quotation")


@app.route("/owner/documents/<document_id>")
@owner_required
def owner_document_detail(document_id):
    owner, business, site, subscription, trial = get_owner_context()
    verification = fetch_business_verification(business["id"]) or {}
    document, items = fetch_document(document_id)
    if not document or str(document["business_id"]) != str(business["id"]):
        abort(404)
    return render_template("owner/document_detail.html", owner=owner, business=business, document=document, items=items, trial=trial, verification=verification)


@app.route("/owner/documents/<document_id>/download")
@owner_required
def owner_document_download(document_id):
    owner, business, site, subscription, trial = get_owner_context()
    document, items = fetch_document(document_id)
    if not document or str(document["business_id"]) != str(business["id"]):
        abort(404)
    body, status_code, headers = document_pdf_response(business, document, items)
    return body, status_code, headers


@app.route("/customer/register", methods=["GET", "POST"])
def customer_register():
    business, site = current_business_context(require_subdomain=True)
    if not business or not business.get("id"):
        return redirect(url_for("template_gallery"))
    error = None
    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        if not email:
            error = "Email is required."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif password != confirm_password:
            error = "Password and confirm password must match."
        else:
            conn = db()
            cur = conn.cursor()
            cur.execute("SELECT id FROM customer_accounts WHERE business_id=%s AND email=%s LIMIT 1", (business["id"], email))
            if cur.fetchone():
                error = "That email is already registered for this business."
            else:
                cur.execute(
                    """
                    INSERT INTO customer_accounts
                    (business_id, full_name, email, phone, password_hash)
                    VALUES (%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (business["id"], full_name, email, phone, generate_password_hash(password)),
                )
                customer_id = cur.fetchone()["id"]
                conn.commit()
                session["customer_id"] = str(customer_id)
                session["customer_business_id"] = str(business["id"])
                cur.close()
                conn.close()
                return redirect(url_for("customer_dashboard"))
            cur.close()
            conn.close()
    return render_template("customer/register.html", business=business, site=site, error=error)


@app.route("/customer/login", methods=["GET", "POST"])
def customer_login():
    business, site = current_business_context(require_subdomain=True)
    if not business or not business.get("id"):
        return redirect(url_for("template_gallery"))
    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        conn = db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM customer_accounts WHERE business_id=%s AND email=%s LIMIT 1", (business["id"], email))
        customer = cur.fetchone()
        cur.close()
        conn.close()
        if customer and check_password_hash(customer["password_hash"], password):
            session["customer_id"] = str(customer["id"])
            session["customer_business_id"] = str(business["id"])
            return redirect(request.args.get("next") or url_for("customer_dashboard"))
        error = "Invalid email or password."
    return render_template("customer/login.html", business=business, site=site, error=error)


@app.route("/customer/logout")
def customer_logout():
    session.pop("customer_id", None)
    session.pop("customer_business_id", None)
    business, _ = current_business_context(require_subdomain=False)
    if business:
        return redirect(url_for("customer_login"))
    return redirect(url_for("home"))


@app.route("/customer/dashboard")
@customer_required
def customer_dashboard():
    customer, business = get_current_customer()
    _, site = current_business_context(require_subdomain=False)
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_orders WHERE business_id=%s AND customer_id=%s ORDER BY created_at DESC", (business["id"], customer["id"]))
    orders = cur.fetchall()
    cur.execute(
        """
        SELECT * FROM business_documents
        WHERE business_id=%s AND (
            LOWER(COALESCE(customer_email, '')) = LOWER(%s) OR COALESCE(customer_phone, '') = %s
        )
        ORDER BY created_at DESC
        """,
        (business["id"], customer.get("email") or "", customer.get("phone") or ""),
    )
    documents = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("customer/dashboard.html", customer=customer, business=business, site=site, orders=orders, documents=documents)


@app.route("/customer/orders")
@customer_required
def customer_orders():
    customer, business = get_current_customer()
    _, site = current_business_context(require_subdomain=False)
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM business_orders WHERE business_id=%s AND customer_id=%s ORDER BY created_at DESC", (business["id"], customer["id"]))
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("customer/orders.html", customer=customer, business=business, site=site, orders=orders)


@app.route("/free-tools")
def free_tools_index():
    return render_template(
        "free_tools/index.html",
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/free-tools/templates")
def free_tools_template_root():
    return redirect(url_for("free_tools_invoice_templates"))


@app.route("/free-tools/templates/invoices")
def free_tools_invoice_templates():
    return free_tools_template_gallery("invoice")


@app.route("/free-tools/templates/quotations")
def free_tools_quotation_templates():
    return free_tools_template_gallery("quotation")


def free_tools_template_gallery(document_type):
    return render_template(
        "free_tools/template_gallery.html",
        templates=free_tool_templates(document_type),
        document_type=document_type,
        user_logged_in=free_tool_logged_in(),
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/free-tools/templates/<doc_type>/<template_slug>")
def free_tools_template_preview(doc_type, template_slug):
    doc_type, template_slug = normalize_document_template(doc_type[:-1] if doc_type.endswith("s") else doc_type, template_slug)
    meta = free_tool_template_meta(template_slug, doc_type)
    if not meta:
        abort(404)
    context = build_document_context(
        template_slug=template_slug,
        document_type=doc_type,
        business_data={"business_name": "VibeHost Business", "business_email": "hello@vibehostbusiness.com", "business_phone": "+264 81 000 0000", "business_address": "Windhoek, Namibia"},
        watermark=True,
        form_data={
            "business_name": "VibeHost Business",
            "business_email": "hello@vibehostbusiness.com",
            "business_phone": "+264 81 000 0000",
            "business_address": "Windhoek, Namibia",
            "customer_name": "Customer Name",
            "customer_email": "customer@example.com",
            "customer_phone": "+264 81 000 0000",
            "customer_address": "Client address",
            "notes": "This sample preview shows how the selected template will look with your own business details.",
            "terms": "Payment is due according to the dates shown on the document.",
            "payment_details": "Bank transfer details go here.",
            "due_date": "2026-06-01",
            "valid_until": "2026-06-01",
            "item_name": ["Service package", "Priority support", "Delivery charge"],
            "quantity": ["2", "1", "1"],
            "unit_price": ["650", "250", "80"],
            "tax_percentage": "15",
            "discount": "0",
        },
    )
    use_link = url_for(f"free_tools_create_{doc_type}", template=template_slug) if free_tool_logged_in() else url_for("free_tools_register", template=template_slug)
    toolbar = f"""
    <div style="position:fixed;right:18px;top:18px;z-index:9999;display:flex;gap:10px;flex-wrap:wrap">
      <a href="{url_for('free_tools_invoice_templates' if doc_type == 'invoice' else 'free_tools_quotation_templates')}" style="padding:12px 16px;border-radius:999px;background:#ffffff;color:#111827;text-decoration:none;font-weight:700;box-shadow:0 12px 32px rgba(15,23,42,.16)">All templates</a>
      <a href="{use_link}" style="padding:12px 16px;border-radius:999px;background:#111827;color:#ffffff;text-decoration:none;font-weight:700;box-shadow:0 12px 32px rgba(15,23,42,.28)">Use this template</a>
    </div>
    """
    return render_free_tool_document(template_slug, context, toolbar)


@app.route("/free-tools/sample/<doc_type>/<template_slug>", methods=["GET", "POST"])
def free_tools_sample(doc_type, template_slug):
    doc_type, template_slug = normalize_document_template(doc_type, template_slug)
    meta = free_tool_template_meta(template_slug, doc_type)
    if not meta:
        abort(404)
    logo_url = None
    if request.method == "POST":
        logo_url = upload_logo(request.files.get("business_logo"), subdir="free_tools")
    context = build_document_context(
        template_slug=template_slug,
        document_type=request.form.get("document_type") if request.method == "POST" else doc_type,
        business_data={
            "business_name": request.form.get("business_name") if request.method == "POST" else "VibeHost Business",
            "business_logo_url": logo_url,
            "business_email": request.form.get("business_email") if request.method == "POST" else "hello@vibehostbusiness.com",
            "business_phone": request.form.get("business_phone") if request.method == "POST" else "+264 81 000 0000",
            "business_address": request.form.get("business_address") if request.method == "POST" else "Windhoek, Namibia",
            "business_tax_number": request.form.get("business_tax_number") if request.method == "POST" else "",
            "payment_details": request.form.get("payment_details") if request.method == "POST" else "Bank transfer details go here.",
        },
        watermark=True,
        form_data=request.form if request.method == "POST" else {
            "document_type": doc_type,
            "business_name": "VibeHost Business",
            "business_email": "hello@vibehostbusiness.com",
            "business_phone": "+264 81 000 0000",
            "business_address": "Windhoek, Namibia",
            "customer_name": "Customer Name",
            "customer_email": "customer@example.com",
            "customer_phone": "+264 81 000 0000",
            "customer_address": "Client address",
            "notes": "This sample preview helps you see your content before creating a free account.",
            "terms": "Payment and approval terms appear here.",
            "item_name": ["Consultation package", "Delivery support", "Priority handling"],
            "quantity": ["1", "2", "1"],
            "unit_price": ["850", "250", "120"],
            "tax_percentage": "15",
            "discount": "0",
        },
    )
    return render_template(
        "free_tools/sample_creator.html",
        template_meta=meta,
        document_type=doc_type,
        template_slug=template_slug,
        preview_html=render_free_tool_document(template_slug, context),
        support_phone=SUPPORT_PHONE,
        support_whatsapp_url=SUPPORT_WHATSAPP_URL,
    )


@app.route("/free-tools/sample/<doc_type>/<template_slug>/download", methods=["GET", "POST"])
def free_tools_sample_download(doc_type, template_slug):
    doc_type, template_slug = normalize_document_template(doc_type, template_slug)
    logo_url = upload_logo(request.files.get("business_logo"), subdir="free_tools") if request.method == "POST" else None
    context = build_document_context(
        template_slug=template_slug,
        document_type=request.values.get("document_type") or doc_type,
        business_data={
            "business_name": request.values.get("business_name") or "VibeHost Business",
            "business_logo_url": logo_url,
            "business_email": request.values.get("business_email") or "hello@vibehostbusiness.com",
            "business_phone": request.values.get("business_phone") or "+264 81 000 0000",
            "business_address": request.values.get("business_address") or "",
            "business_tax_number": request.values.get("business_tax_number") or "",
            "payment_details": request.values.get("payment_details") or "",
        },
        watermark=True,
        form_data=request.values if request.values else {"document_type": doc_type},
    )
    document = {
        **context,
        "template_slug": template_slug,
        "document_type": context["document_type"],
        "document_number": context["document_number"],
    }
    pdf_bytes = generate_document_pdf(document, context["items"], watermark_label="VibeHost Watermark")
    filename = f"{context['document_type']}-{context['document_number']}.pdf"
    return pdf_bytes, 200, {"Content-Type": "application/pdf", "Content-Disposition": f"inline; filename={filename}"}


@app.route("/free-tools/register", methods=["GET", "POST"])
def free_tools_register():
    error = None
    template_slug = request.args.get("template") or request.form.get("selected_template") or "invoice_modern_clean"
    if not free_tool_template_meta(template_slug):
        template_slug = "invoice_modern_clean"
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        full_name = (request.form.get("full_name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        if not full_name:
            error = "Full name is required."
        elif not email:
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
                invoice_template = template_slug if template_slug.startswith("invoice_") else "invoice_modern_clean"
                quotation_template = f"quotation_{template_slug.split('_', 1)[1]}" if template_slug.startswith("invoice_") else template_slug
                if not quotation_template.startswith("quotation_"):
                    quotation_template = "quotation_modern_clean"
                cur.execute(
                    """
                    INSERT INTO free_tool_users
                    (email, password_hash, full_name, phone, provider, plan_name, selected_template, selected_invoice_template, selected_quotation_template)
                    VALUES (%s,%s,%s,%s,'email','free',%s,%s,%s)
                    RETURNING id
                    """,
                    (email, generate_password_hash(password), full_name, phone, template_slug, invoice_template, quotation_template),
                )
                user_id = cur.fetchone()["id"]
                conn.commit()
                session["free_tool_user_id"] = str(user_id)
                cur.close()
                conn.close()
                return redirect(url_for("free_tools_dashboard"))
            cur.close()
            conn.close()
    return render_template(
        "free_tools/auth.html",
        mode="register",
        error=error,
        template_slug=template_slug,
        templates=free_tool_templates("invoice"),
        google_available=auth_provider_available("google"),
        facebook_available=auth_provider_available("facebook"),
    )


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
    return render_template(
        "free_tools/auth.html",
        mode="login",
        error=error,
        google_available=auth_provider_available("google"),
        facebook_available=auth_provider_available("facebook"),
    )


@app.route("/auth/supabase/google")
def auth_supabase_google():
    return auth_supabase_provider("google")


@app.route("/auth/supabase/facebook")
def auth_supabase_facebook():
    return auth_supabase_provider("facebook")


def auth_supabase_provider(provider):
    context = request.args.get("context", "free_tools")
    if not auth_provider_available(provider):
        return render_template("free_tools/social_not_ready.html", context=context)
    try:
        client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
        redirect_to = url_for("auth_supabase_callback", _external=True)
        response = client.auth.sign_in_with_oauth({"provider": provider, "options": {"redirect_to": redirect_to}})
        session["oauth_context"] = context
        auth_url = getattr(response, "url", None) or response.get("url")
        return redirect(auth_url)
    except Exception:
        return render_template("free_tools/social_not_ready.html", context=context)


def _supabase_attr(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


@app.route("/auth/supabase/callback")
def auth_supabase_callback():
    context = session.get("oauth_context", "free_tools")
    if not auth_provider_available("google"):
        return render_template("free_tools/social_not_ready.html", context=context, callback=True)
    try:
        client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
        code = request.args.get("code")
        if code and hasattr(client.auth, "exchange_code_for_session"):
            client.auth.exchange_code_for_session(code)
        user_response = client.auth.get_user() if hasattr(client.auth, "get_user") else None
        raw_user = _supabase_attr(user_response, "user")
        email = (_supabase_attr(raw_user, "email") or "").strip().lower()
        metadata = _supabase_attr(raw_user, "user_metadata", {}) or {}
        full_name = (metadata.get("full_name") or metadata.get("name") or email.split("@")[0] or "VibeHost User").strip()
        provider = request.args.get("provider") or metadata.get("provider_id") or "oauth"
        if not email:
            return render_template("free_tools/social_not_ready.html", context=context, callback=True)

        conn = db()
        cur = conn.cursor()
        if context == "owner":
            cur.execute("SELECT * FROM business_owners WHERE email=%s LIMIT 1", (email,))
            owner = cur.fetchone()
            if owner:
                cur.execute("SELECT verification_status FROM business_profiles WHERE id=%s LIMIT 1", (owner["business_id"],))
                business = cur.fetchone()
                session["owner_id"] = str(owner["id"])
                session["business_id"] = str(owner["business_id"])
                cur.close()
                conn.close()
                return redirect(url_for("owner_dashboard") if (business or {}).get("verification_status") == "approved" else url_for("owner_verification_status"))
            cur.close()
            conn.close()
            return render_template("free_tools/social_not_ready.html", context=context, callback=True, email=email)

        cur.execute("SELECT * FROM free_tool_users WHERE email=%s LIMIT 1", (email,))
        user = cur.fetchone()
        if not user:
            cur.execute(
                """
                INSERT INTO free_tool_users
                (email, password_hash, full_name, provider, plan_name, selected_template, selected_invoice_template, selected_quotation_template)
                VALUES (%s,%s,%s,%s,'free','invoice_modern_clean','invoice_modern_clean','quotation_modern_clean')
                RETURNING id
                """,
                (email, generate_password_hash(uuid.uuid4().hex), full_name, provider),
            )
            user_id = cur.fetchone()["id"]
            conn.commit()
        else:
            user_id = user["id"]
        cur.close()
        conn.close()
        session["free_tool_user_id"] = str(user_id)
        return redirect(url_for("free_tools_dashboard"))
    except Exception:
        return render_template("free_tools/social_not_ready.html", context=context, callback=True)


@app.route("/free-tools/logout")
def free_tools_logout():
    session.pop("free_tool_user_id", None)
    return redirect(url_for("free_tools_login"))


@app.route("/free-tools/dashboard")
@free_tool_required
def free_tools_dashboard():
    user = get_free_tool_user()
    invoices, quotations = free_tool_counts(user["id"])
    recent_documents = fetch_free_tool_documents(user["id"], limit=6)
    return render_template(
        "free_tools/dashboard.html",
        user=user,
        invoices=invoices,
        quotations=quotations,
        invoice_template_meta=free_tool_template_meta(user.get("selected_invoice_template") or "invoice_modern_clean", "invoice"),
        quotation_template_meta=free_tool_template_meta(user.get("selected_quotation_template") or "quotation_modern_clean", "quotation"),
        recent_documents=recent_documents,
        watermark_on=user.get("plan_name", "free") == "free",
        limit=FREE_TOOL_DOCUMENT_LIMIT,
    )


@app.route("/free-tools/profile", methods=["GET", "POST"])
@free_tool_required
def free_tools_profile():
    user = get_free_tool_user()
    success = None
    if request.method == "POST":
        logo_url = upload_logo(request.files.get("business_logo")) or user.get("business_logo_url")
        conn = db()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE free_tool_users
            SET business_name=%s, business_logo_url=%s, business_phone=%s,
                business_address=%s, business_tax_number=%s, payment_details=%s,
                selected_invoice_template=%s, selected_quotation_template=%s
            WHERE id=%s
            """,
            (
                (request.form.get("business_name") or "").strip(),
                logo_url,
                (request.form.get("business_phone") or "").strip(),
                (request.form.get("business_address") or "").strip(),
                (request.form.get("business_tax_number") or "").strip(),
                (request.form.get("payment_details") or "").strip(),
                request.form.get("selected_invoice_template") or user.get("selected_invoice_template") or "invoice_modern_clean",
                request.form.get("selected_quotation_template") or user.get("selected_quotation_template") or "quotation_modern_clean",
                user["id"],
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        success = "Profile updated successfully."
        user = get_free_tool_user()
    return render_template("free_tools/profile.html", user=user, success=success, invoice_templates=free_tool_templates("invoice"), quotation_templates=free_tool_templates("quotation"))


@app.route("/free-tools/create", methods=["GET", "POST"])
@free_tool_required
def free_tools_create():
    user = get_free_tool_user()
    template_slug = request.args.get("template") or request.form.get("template_slug") or user.get("selected_invoice_template") or "invoice_modern_clean"
    document_type = request.args.get("type") or request.form.get("document_type") or "invoice"
    if document_type not in {"invoice", "quotation"}:
        document_type = "invoice"
    if not free_tool_template_meta(template_slug):
        template_slug = user.get("selected_quotation_template") if document_type == "quotation" else user.get("selected_invoice_template")
    if not template_slug:
        template_slug = "quotation_modern_clean" if document_type == "quotation" else "invoice_modern_clean"
    target_column = "selected_quotation_template" if document_type == "quotation" else "selected_invoice_template"
    if user.get(target_column) != template_slug:
        conn = db()
        cur = conn.cursor()
        cur.execute(f"UPDATE free_tool_users SET {target_column}=%s, selected_template=%s WHERE id=%s", (template_slug, template_slug, user["id"]))
        conn.commit()
        cur.close()
        conn.close()
        user[target_column] = template_slug
        user["selected_template"] = template_slug
    error = None
    success = None
    created_document_id = None
    if request.method == "POST":
        invoices, quotations = free_tool_counts(user["id"])
        current_count = invoices if document_type == "invoice" else quotations
        if user.get("plan_name", "free") == "free" and current_count >= FREE_TOOL_DOCUMENT_LIMIT:
            error = "Upgrade monthly to keep unlimited invoice and quotation records."
        else:
            conn = db()
            cur = conn.cursor()
            created_document_id = create_free_tool_document_record(cur, user, request.form, template_slug, document_type)
            conn.commit()
            cur.close()
            conn.close()
            success = f"{document_type.title()} created successfully."
            return redirect(url_for("free_tools_document_preview", document_id=created_document_id))
    documents = fetch_free_tool_documents(user["id"], document_type=document_type)
    return render_template(
        "free_tools/create.html",
        user=user,
        templates=free_tool_templates(document_type),
        template_meta=free_tool_template_meta(template_slug, document_type),
        template_slug=template_slug,
        document_type=document_type,
        documents=documents,
        error=error,
        success=success,
        limit=FREE_TOOL_DOCUMENT_LIMIT,
    )


@app.route("/free-tools/create/invoice", methods=["GET", "POST"])
@free_tool_required
def free_tools_create_invoice():
    template_slug = request.args.get("template") or get_free_tool_user().get("selected_invoice_template") or "invoice_modern_clean"
    return redirect(url_for("free_tools_create", template=template_slug, type="invoice", **({} if request.method == "GET" else {})))


@app.route("/free-tools/create/quotation", methods=["GET", "POST"])
@free_tool_required
def free_tools_create_quotation():
    template_slug = request.args.get("template") or get_free_tool_user().get("selected_quotation_template") or "quotation_modern_clean"
    return redirect(url_for("free_tools_create", template=template_slug, type="quotation", **({} if request.method == "GET" else {})))


@app.route("/free-tools/invoices")
@free_tool_required
def free_tools_invoices():
    return redirect(url_for("free_tools_create_invoice"))


@app.route("/free-tools/quotations")
@free_tool_required
def free_tools_quotations():
    return redirect(url_for("free_tools_create_quotation"))


@app.route("/free-tools/documents/<document_id>")
@free_tool_required
def free_tools_document_preview(document_id):
    user = get_free_tool_user()
    document, items = fetch_free_tool_document(document_id, user["id"])
    if not document:
        abort(404)
    document = dict(document)
    if user.get("plan_name") != "free":
        document["watermark"] = False
    context = build_document_context(
        template_slug=document.get("template_slug"),
        saved_document=document,
        saved_items=items,
        business_name=document.get("business_name") or user.get("full_name") or "VibeHost Business",
    )
    toolbar = f"""
    <div style="position:fixed;right:18px;top:18px;z-index:9999;display:flex;gap:10px;flex-wrap:wrap">
      <a href="{url_for('free_tools_dashboard')}" style="padding:12px 16px;border-radius:999px;background:#ffffff;color:#111827;text-decoration:none;font-weight:700;box-shadow:0 12px 32px rgba(15,23,42,.16)">Dashboard</a>
      <a href="{url_for('free_tools_document_download', document_id=document_id)}" style="padding:12px 16px;border-radius:999px;background:#111827;color:#ffffff;text-decoration:none;font-weight:700;box-shadow:0 12px 32px rgba(15,23,42,.28)">Download</a>
    </div>
    """
    return render_free_tool_document(document.get("template_slug"), context, toolbar)


@app.route("/free-tools/documents/<document_id>/download")
@free_tool_required
def free_tools_document_download(document_id):
    user = get_free_tool_user()
    document, items = fetch_free_tool_document(document_id, user["id"])
    if not document:
        abort(404)
    document = dict(document)
    if user.get("plan_name") != "free":
        document["watermark"] = False
    body, status_code, headers = free_tool_document_pdf_response(user, document, items)
    return body, status_code, headers


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
    app.run(debug=os.getenv("FLASK_DEBUG") == "1", port=int(os.getenv("PORT", "5055")))
