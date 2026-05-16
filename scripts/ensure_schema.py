import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(".env"))

TEMPLATES = [
    ("Retail Shop", "retail-shop", "retail", "Product catalog, featured deals, WhatsApp orders and a polished storefront."),
    ("Restaurant and Food", "restaurant-food", "food", "Menus, meal promotions, delivery flow and table or catering enquiries."),
    ("Transport and Shuttle", "transport-shuttle", "transport", "Airport transfers, route cards, booking requests and operator tools."),
    ("Guesthouse and Lodge", "guesthouse-lodge", "hospitality", "Room previews, stay enquiries, amenity highlights and booking prompts."),
    ("Salon and Beauty", "salon-beauty", "beauty", "Hair, nails, makeup and appointment-driven service presentation."),
    ("School and Education", "school-education", "education", "Admissions, parent communication, notices and academic feature blocks."),
    ("Health and Wellness", "health-wellness", "health", "Consultation enquiries, wellness services and clinic-style credibility."),
    ("Construction and Repair", "construction", "construction", "Project showcases, quotation flows and contractor-oriented service pages."),
    ("Cleaning Services", "cleaning-services", "services", "Recurring plans, quote requests, service packages and cleaning teams."),
]


def main():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO public")
                cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS business_profiles (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_name TEXT,
                        owner_name TEXT,
                        category TEXT,
                        phone TEXT,
                        whatsapp TEXT,
                        email TEXT,
                        logo_url TEXT,
                        subdomain TEXT UNIQUE,
                        region TEXT,
                        town TEXT,
                        website_type TEXT,
                        description TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS business_sites (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID REFERENCES business_profiles(id) ON DELETE CASCADE,
                        site_title TEXT,
                        template_name TEXT,
                        primary_color TEXT,
                        secondary_color TEXT,
                        accent_color TEXT,
                        hero_title TEXT,
                        hero_subtitle TEXT,
                        background_image TEXT,
                        published BOOLEAN DEFAULT FALSE,
                        font_style TEXT,
                        wallpaper_style TEXT,
                        show_services BOOLEAN DEFAULT TRUE,
                        show_gallery BOOLEAN DEFAULT TRUE,
                        show_booking BOOLEAN DEFAULT TRUE,
                        show_whatsapp BOOLEAN DEFAULT TRUE,
                        live_url TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID REFERENCES business_profiles(id) ON DELETE CASCADE,
                        plan_name TEXT,
                        status TEXT,
                        trial_started_at TIMESTAMPTZ,
                        trial_expires_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS business_owners (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID REFERENCES business_profiles(id) ON DELETE CASCADE,
                        owner_name TEXT,
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT,
                        role TEXT DEFAULT 'owner',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS business_products (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID,
                        name TEXT,
                        description TEXT,
                        category TEXT,
                        price NUMERIC DEFAULT 0,
                        image_url TEXT,
                        stock_quantity INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS business_orders (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID,
                        customer_name TEXT,
                        customer_email TEXT,
                        customer_phone TEXT,
                        order_type TEXT,
                        message TEXT,
                        status TEXT DEFAULT 'new',
                        total_amount NUMERIC DEFAULT 0,
                        source TEXT DEFAULT 'website',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS business_documents (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id TEXT,
                        document_type TEXT CHECK (document_type IN ('invoice','quotation')),
                        document_number TEXT,
                        customer_name TEXT,
                        customer_email TEXT,
                        customer_phone TEXT,
                        notes TEXT,
                        subtotal NUMERIC DEFAULT 0,
                        tax NUMERIC DEFAULT 0,
                        total NUMERIC DEFAULT 0,
                        status TEXT DEFAULT 'draft',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS business_document_items (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        document_id UUID,
                        item_name TEXT,
                        quantity NUMERIC DEFAULT 1,
                        unit_price NUMERIC DEFAULT 0,
                        total NUMERIC DEFAULT 0,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS free_tool_users (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email TEXT UNIQUE,
                        password_hash TEXT,
                        full_name TEXT,
                        provider TEXT DEFAULT 'email',
                        plan_name TEXT DEFAULT 'free',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS site_services (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id TEXT,
                        site_id TEXT,
                        title TEXT,
                        description TEXT,
                        price TEXT,
                        active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS site_gallery (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id TEXT,
                        site_id TEXT,
                        image_url TEXT,
                        caption TEXT,
                        sort_order INTEGER DEFAULT 0,
                        active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS website_templates (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        name TEXT,
                        slug TEXT UNIQUE,
                        category TEXT,
                        description TEXT,
                        active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                alter_statements = [
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS business_name TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS owner_name TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS category TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS phone TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS whatsapp TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS email TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS logo_url TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS subdomain TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS region TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS town TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS website_type TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS description TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS site_title TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS template_name TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS primary_color TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS secondary_color TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS accent_color TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS hero_title TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS hero_subtitle TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS background_image TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS published BOOLEAN DEFAULT FALSE",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS font_style TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS wallpaper_style TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS show_services BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS show_gallery BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS show_booking BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS show_whatsapp BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS live_url TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS plan_name TEXT",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS status TEXT",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS trial_started_at TIMESTAMPTZ",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS trial_expires_at TIMESTAMPTZ",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_owners ADD COLUMN IF NOT EXISTS owner_name TEXT",
                    "ALTER TABLE business_owners ADD COLUMN IF NOT EXISTS email TEXT",
                    "ALTER TABLE business_owners ADD COLUMN IF NOT EXISTS password_hash TEXT",
                    "ALTER TABLE business_owners ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'owner'",
                    "ALTER TABLE business_owners ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_products ADD COLUMN IF NOT EXISTS business_id UUID",
                    "ALTER TABLE business_products ADD COLUMN IF NOT EXISTS name TEXT",
                    "ALTER TABLE business_products ADD COLUMN IF NOT EXISTS description TEXT",
                    "ALTER TABLE business_products ADD COLUMN IF NOT EXISTS category TEXT",
                    "ALTER TABLE business_products ADD COLUMN IF NOT EXISTS price NUMERIC DEFAULT 0",
                    "ALTER TABLE business_products ADD COLUMN IF NOT EXISTS image_url TEXT",
                    "ALTER TABLE business_products ADD COLUMN IF NOT EXISTS stock_quantity INTEGER DEFAULT 0",
                    "ALTER TABLE business_products ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'",
                    "ALTER TABLE business_products ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS business_id UUID",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS customer_name TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS customer_email TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS customer_phone TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS order_type TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS message TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'new'",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS total_amount NUMERIC DEFAULT 0",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'website'",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS business_id TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS document_type TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS document_number TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS customer_name TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS customer_email TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS customer_phone TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS notes TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS subtotal NUMERIC DEFAULT 0",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS tax NUMERIC DEFAULT 0",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS total NUMERIC DEFAULT 0",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'draft'",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS document_id UUID",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS item_name TEXT",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS quantity NUMERIC DEFAULT 1",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS unit_price NUMERIC DEFAULT 0",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS total NUMERIC DEFAULT 0",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS email TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS password_hash TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS full_name TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS provider TEXT DEFAULT 'email'",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS plan_name TEXT DEFAULT 'free'",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE site_services ADD COLUMN IF NOT EXISTS business_id TEXT",
                    "ALTER TABLE site_services ADD COLUMN IF NOT EXISTS site_id TEXT",
                    "ALTER TABLE site_services ADD COLUMN IF NOT EXISTS title TEXT",
                    "ALTER TABLE site_services ADD COLUMN IF NOT EXISTS description TEXT",
                    "ALTER TABLE site_services ADD COLUMN IF NOT EXISTS price TEXT",
                    "ALTER TABLE site_services ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE site_services ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE site_gallery ADD COLUMN IF NOT EXISTS business_id TEXT",
                    "ALTER TABLE site_gallery ADD COLUMN IF NOT EXISTS site_id TEXT",
                    "ALTER TABLE site_gallery ADD COLUMN IF NOT EXISTS image_url TEXT",
                    "ALTER TABLE site_gallery ADD COLUMN IF NOT EXISTS caption TEXT",
                    "ALTER TABLE site_gallery ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0",
                    "ALTER TABLE site_gallery ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE site_gallery ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE website_templates ADD COLUMN IF NOT EXISTS name TEXT",
                    "ALTER TABLE website_templates ADD COLUMN IF NOT EXISTS slug TEXT",
                    "ALTER TABLE website_templates ADD COLUMN IF NOT EXISTS category TEXT",
                    "ALTER TABLE website_templates ADD COLUMN IF NOT EXISTS description TEXT",
                    "ALTER TABLE website_templates ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE website_templates ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                ]
                for statement in alter_statements:
                    cur.execute(statement)

                for name, slug, category, description in TEMPLATES:
                    cur.execute(
                        """
                        INSERT INTO website_templates (name, slug, category, description, active)
                        VALUES (%s,%s,%s,%s,TRUE)
                        ON CONFLICT (slug) DO UPDATE
                        SET name=EXCLUDED.name,
                            category=EXCLUDED.category,
                            description=EXCLUDED.description,
                            active=TRUE
                        """,
                        (name, slug, category, description),
                    )

        print("Schema ensured successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
