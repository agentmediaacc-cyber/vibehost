import os
import sys
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(".env"))
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASE_URL = "http://127.0.0.1:5055"
PUBLIC_ROUTES = [
    "/",
    "/healthz",
    "/preview",
    "/templates",
    "/templates/preview/retail-shop",
    "/builder/create/retail-shop",
    "/owner/login",
    "/free-tools",
    "/free-tools/templates/invoices",
    "/free-tools/templates/quotations",
]
REQUIRED_TABLES = [
    "master_admins",
    "business_profiles",
    "business_owners",
    "subscriptions",
    "payments",
    "system_settings",
    "business_products",
    "business_orders",
    "business_documents",
    "business_document_items",
    "business_verifications",
    "customer_accounts",
    "stock_movements",
    "business_staff",
    "business_adverts",
]


def print_result(ok, label, detail=""):
    status = "OK" if ok else "FAIL"
    suffix = f" {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")


def test_db():
    print("\n--- Testing Database ---")
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM website_templates")
            count = cur.fetchone()[0]
            print_result(True, "Neon Connection")
            print_result(count >= 9, "website_templates count", str(count))
            for table in REQUIRED_TABLES:
                cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name=%s)", (table,))
                exists = cur.fetchone()[0]
                print_result(exists, f"Table '{table}' exists")
        conn.close()
        return True
    except Exception as exc:
        print_result(False, "Database test failed", str(exc))
        return False


def test_routes_requests():
    print("\n--- Testing HTTP Routes ---")
    for route in PUBLIC_ROUTES:
        resp = requests.get(f"{BASE_URL}{route}", timeout=5)
        print_result(resp.status_code == 200, route, f"(Status: {resp.status_code})")
    redirect_cases = [
        ("/owner/dashboard", "/owner/login"),
        ("/master/dashboard", "/owner/login"),
        ("/customer/dashboard", "/customer/login"),
    ]
    for route, expected in redirect_cases:
        resp = requests.get(f"{BASE_URL}{route}", allow_redirects=False, timeout=5)
        ok = resp.status_code in (301, 302) and expected in resp.headers.get("Location", "")
        print_result(ok, route, f"(Status: {resp.status_code}, Location: {resp.headers.get('Location')})")


def test_routes_flask():
    print("\n--- Testing Flask test_client Routes ---")
    import app as app_module

    flask_app = app_module.app
    print_result(True, "App imports successfully")

    rules = list(flask_app.url_map.iter_rules())
    endpoints = [rule.endpoint for rule in rules]
    print_result(len(rules) > 0, "Routes loaded", str(len(rules)))
    print_result(endpoints.count("template_gallery") == 2, "Shared template gallery endpoint registered")

    with flask_app.test_client() as client:
        for route in PUBLIC_ROUTES:
            resp = client.get(route)
            print_result(resp.status_code == 200, route, f"(Status: {resp.status_code})")

        redirect_cases = [
            ("/owner/dashboard", "/owner/login"),
            ("/owner/onboarding", "/owner/login"),
            ("/owner/verification", "/owner/login"),
            ("/owner/verification/status", "/owner/login"),
            ("/master/dashboard", "/owner/login"),
            ("/master/verifications", "/owner/login"),
            ("/customer/dashboard", "/customer/login"),
            ("/customer/orders", "/customer/login"),
        ]
        for route, expected in redirect_cases:
            resp = client.get(route, follow_redirects=False)
            ok = resp.status_code in (301, 302) and expected in resp.headers.get("Location", "")
            print_result(ok, route, f"(Status: {resp.status_code}, Location: {resp.headers.get('Location')})")

        customer_routes = [
            "/customer/register",
            "/customer/login",
        ]
        for route in customer_routes:
            resp = client.get(route, follow_redirects=False)
            ok = resp.status_code in (200, 301, 302)
            print_result(ok, route, f"(Status: {resp.status_code})")

        preview_resp = client.get("/templates/preview/retail-shop")
        preview_html = preview_resp.get_data(as_text=True)
        print_result("Customer Login" in preview_html, "Retail preview includes customer login link")
        print_result("Create Account" in preview_html, "Retail preview includes customer register link")
        print_result("Send enquiry" in preview_html or "Please contact the business directly" in preview_html, "Retail preview enquiry section renders")

        free_tools_invoice = client.get("/free-tools/templates/invoices")
        free_tools_quote = client.get("/free-tools/templates/quotations")
        print_result(free_tools_invoice.status_code == 200, "/free-tools/templates/invoices", f"(Status: {free_tools_invoice.status_code})")
        print_result(free_tools_quote.status_code == 200, "/free-tools/templates/quotations", f"(Status: {free_tools_quote.status_code})")

        health = client.get("/healthz")
        health_json = health.get_json(silent=True) or {}
        print_result(health.status_code == 200 and health_json.get("status") == "ok", "/healthz", str(health_json))


if __name__ == "__main__":
    test_db()
    try:
        requests.get(BASE_URL, timeout=2)
        test_routes_requests()
    except Exception:
        print("\n[INFO] Live server not available, using Flask test_client fallback.")
        test_routes_flask()
