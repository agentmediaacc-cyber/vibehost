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

                # New Tables
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS master_admins (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        email TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        full_name TEXT,
                        role TEXT DEFAULT 'master_admin',
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS payments (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID NULL,
                        free_tool_user_id UUID NULL,
                        amount NUMERIC DEFAULT 0,
                        currency TEXT DEFAULT 'NAD',
                        payment_type TEXT,
                        payment_method TEXT,
                        status TEXT DEFAULT 'pending',
                        reference TEXT,
                        notes TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS system_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                # Existing Tables
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
                        business_tax_number TEXT,
                        payment_details TEXT,
                        selected_invoice_template TEXT DEFAULT 'invoice_modern_clean',
                        selected_quotation_template TEXT DEFAULT 'quotation_modern_clean',
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
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
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
                        email_verified BOOLEAN DEFAULT FALSE,
                        phone TEXT,
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
                        customer_id UUID,
                        customer_email TEXT,
                        customer_phone TEXT,
                        order_type TEXT,
                        message TEXT,
                        status TEXT DEFAULT 'new',
                        total_amount NUMERIC DEFAULT 0,
                        source TEXT DEFAULT 'website',
                        delivery_method TEXT,
                        delivery_address TEXT,
                        delivery_time TEXT,
                        assigned_staff TEXT,
                        delivery_status TEXT DEFAULT 'pending',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS business_verifications (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID,
                        owner_id UUID,
                        business_registration_url TEXT,
                        owner_id_url TEXT,
                        proof_of_address_url TEXT,
                        status TEXT DEFAULT 'pending',
                        admin_notes TEXT,
                        reviewed_by UUID,
                        reviewed_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS customer_accounts (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID,
                        full_name TEXT,
                        email TEXT,
                        phone TEXT,
                        password_hash TEXT,
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
                        business_name TEXT,
                        business_logo_url TEXT,
                        business_email TEXT,
                        business_phone TEXT,
                        business_address TEXT,
                        business_tax_number TEXT,
                        payment_details TEXT,
                        customer_name TEXT,
                        customer_email TEXT,
                        customer_phone TEXT,
                        customer_address TEXT,
                        notes TEXT,
                        due_date DATE,
                        valid_until DATE,
                        terms TEXT,
                        template_slug TEXT,
                        subtotal NUMERIC DEFAULT 0,
                        tax NUMERIC DEFAULT 0,
                        discount NUMERIC DEFAULT 0,
                        total NUMERIC DEFAULT 0,
                        watermark BOOLEAN DEFAULT TRUE,
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
                    CREATE TABLE IF NOT EXISTS stock_movements (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID,
                        product_id UUID,
                        movement_type TEXT,
                        quantity INTEGER DEFAULT 0,
                        note TEXT,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS business_staff (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID,
                        full_name TEXT,
                        email TEXT,
                        phone TEXT,
                        role TEXT,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS business_adverts (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID,
                        title TEXT,
                        description TEXT,
                        image_url TEXT,
                        button_text TEXT,
                        button_url TEXT,
                        status TEXT DEFAULT 'active',
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
                        phone TEXT,
                        business_name TEXT,
                        business_logo_url TEXT,
                        business_phone TEXT,
                        business_address TEXT,
                        business_tax_number TEXT,
                        payment_details TEXT,
                        provider TEXT DEFAULT 'email',
                        plan_name TEXT DEFAULT 'free',
                        selected_template TEXT DEFAULT 'invoice_modern_clean',
                        selected_invoice_template TEXT DEFAULT 'invoice_modern_clean',
                        selected_quotation_template TEXT DEFAULT 'quotation_modern_clean',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS free_tool_documents (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id UUID REFERENCES free_tool_users(id) ON DELETE CASCADE,
                        template_slug TEXT,
                        document_type TEXT,
                        document_number TEXT,
                        business_name TEXT,
                        business_logo_url TEXT,
                        business_email TEXT,
                        business_phone TEXT,
                        business_address TEXT,
                        business_tax_number TEXT,
                        payment_details TEXT,
                        customer_name TEXT,
                        customer_email TEXT,
                        customer_phone TEXT,
                        customer_address TEXT,
                        notes TEXT,
                        due_date DATE,
                        valid_until DATE,
                        terms TEXT,
                        subtotal NUMERIC DEFAULT 0,
                        tax NUMERIC DEFAULT 0,
                        discount NUMERIC DEFAULT 0,
                        total NUMERIC DEFAULT 0,
                        watermark BOOLEAN DEFAULT TRUE,
                        status TEXT DEFAULT 'draft',
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS free_tool_document_items (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        document_id UUID REFERENCES free_tool_documents(id) ON DELETE CASCADE,
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
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS business_tax_number TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS payment_details TEXT",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS verification_status TEXT DEFAULT 'pending'",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS is_public_active BOOLEAN DEFAULT FALSE",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS selected_invoice_template TEXT DEFAULT 'invoice_modern_clean'",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS selected_quotation_template TEXT DEFAULT 'quotation_modern_clean'",
                    "ALTER TABLE business_profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS site_title TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS template_name TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS primary_color TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS secondary_color TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS accent_color TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS hero_title TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS hero_subtitle TEXT",
                    "ALTER TABLE business_sites ADD COLUMN IF NOT EXISTS homepage_text TEXT",
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
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE master_admins ADD COLUMN IF NOT EXISTS email TEXT",
                    "ALTER TABLE master_admins ADD COLUMN IF NOT EXISTS password_hash TEXT",
                    "ALTER TABLE master_admins ADD COLUMN IF NOT EXISTS full_name TEXT",
                    "ALTER TABLE master_admins ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'master_admin'",
                    "ALTER TABLE master_admins ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE master_admins ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS business_id UUID",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS free_tool_user_id UUID",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS amount NUMERIC DEFAULT 0",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'NAD'",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_type TEXT",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_method TEXT",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS reference TEXT",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS notes TEXT",
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS key TEXT",
                    "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS value TEXT",
                    "ALTER TABLE system_settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_owners ADD COLUMN IF NOT EXISTS owner_name TEXT",
                    "ALTER TABLE business_owners ADD COLUMN IF NOT EXISTS email TEXT",
                    "ALTER TABLE business_owners ADD COLUMN IF NOT EXISTS password_hash TEXT",
                    "ALTER TABLE business_owners ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'owner'",
                    "ALTER TABLE business_owners ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE",
                    "ALTER TABLE business_owners ADD COLUMN IF NOT EXISTS phone TEXT",
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
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS customer_id UUID",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS customer_email TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS customer_phone TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS order_type TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS message TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'new'",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS total_amount NUMERIC DEFAULT 0",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'website'",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS delivery_method TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS delivery_address TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS delivery_time TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS assigned_staff TEXT",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS delivery_status TEXT DEFAULT 'pending'",
                    "ALTER TABLE business_orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS business_id TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS document_type TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS document_number TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS business_name TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS business_logo_url TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS business_email TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS business_phone TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS business_address TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS business_tax_number TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS payment_details TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS customer_name TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS customer_email TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS customer_phone TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS customer_address TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS notes TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS due_date DATE",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS valid_until DATE",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS terms TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS template_slug TEXT",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS subtotal NUMERIC DEFAULT 0",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS tax NUMERIC DEFAULT 0",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS discount NUMERIC DEFAULT 0",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS total NUMERIC DEFAULT 0",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS watermark BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'draft'",
                    "ALTER TABLE business_documents ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS document_id UUID",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS item_name TEXT",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS quantity NUMERIC DEFAULT 1",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS unit_price NUMERIC DEFAULT 0",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS total NUMERIC DEFAULT 0",
                    "ALTER TABLE business_document_items ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_verifications ADD COLUMN IF NOT EXISTS business_id UUID",
                    "ALTER TABLE business_verifications ADD COLUMN IF NOT EXISTS owner_id UUID",
                    "ALTER TABLE business_verifications ADD COLUMN IF NOT EXISTS business_registration_url TEXT",
                    "ALTER TABLE business_verifications ADD COLUMN IF NOT EXISTS owner_id_url TEXT",
                    "ALTER TABLE business_verifications ADD COLUMN IF NOT EXISTS proof_of_address_url TEXT",
                    "ALTER TABLE business_verifications ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'",
                    "ALTER TABLE business_verifications ADD COLUMN IF NOT EXISTS admin_notes TEXT",
                    "ALTER TABLE business_verifications ADD COLUMN IF NOT EXISTS reviewed_by UUID",
                    "ALTER TABLE business_verifications ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ",
                    "ALTER TABLE business_verifications ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE customer_accounts ADD COLUMN IF NOT EXISTS business_id UUID",
                    "ALTER TABLE customer_accounts ADD COLUMN IF NOT EXISTS full_name TEXT",
                    "ALTER TABLE customer_accounts ADD COLUMN IF NOT EXISTS email TEXT",
                    "ALTER TABLE customer_accounts ADD COLUMN IF NOT EXISTS phone TEXT",
                    "ALTER TABLE customer_accounts ADD COLUMN IF NOT EXISTS password_hash TEXT",
                    "ALTER TABLE customer_accounts ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE stock_movements ADD COLUMN IF NOT EXISTS business_id UUID",
                    "ALTER TABLE stock_movements ADD COLUMN IF NOT EXISTS product_id UUID",
                    "ALTER TABLE stock_movements ADD COLUMN IF NOT EXISTS movement_type TEXT",
                    "ALTER TABLE stock_movements ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 0",
                    "ALTER TABLE stock_movements ADD COLUMN IF NOT EXISTS note TEXT",
                    "ALTER TABLE stock_movements ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_staff ADD COLUMN IF NOT EXISTS business_id UUID",
                    "ALTER TABLE business_staff ADD COLUMN IF NOT EXISTS full_name TEXT",
                    "ALTER TABLE business_staff ADD COLUMN IF NOT EXISTS email TEXT",
                    "ALTER TABLE business_staff ADD COLUMN IF NOT EXISTS phone TEXT",
                    "ALTER TABLE business_staff ADD COLUMN IF NOT EXISTS role TEXT",
                    "ALTER TABLE business_staff ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'",
                    "ALTER TABLE business_staff ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE business_adverts ADD COLUMN IF NOT EXISTS business_id UUID",
                    "ALTER TABLE business_adverts ADD COLUMN IF NOT EXISTS title TEXT",
                    "ALTER TABLE business_adverts ADD COLUMN IF NOT EXISTS description TEXT",
                    "ALTER TABLE business_adverts ADD COLUMN IF NOT EXISTS image_url TEXT",
                    "ALTER TABLE business_adverts ADD COLUMN IF NOT EXISTS button_text TEXT",
                    "ALTER TABLE business_adverts ADD COLUMN IF NOT EXISTS button_url TEXT",
                    "ALTER TABLE business_adverts ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'",
                    "ALTER TABLE business_adverts ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS email TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS password_hash TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS full_name TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS phone TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS business_name TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS business_logo_url TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS business_phone TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS business_address TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS business_tax_number TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS payment_details TEXT",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS provider TEXT DEFAULT 'email'",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS plan_name TEXT DEFAULT 'free'",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS selected_template TEXT DEFAULT 'invoice_modern_clean'",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS selected_invoice_template TEXT DEFAULT 'invoice_modern_clean'",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS selected_quotation_template TEXT DEFAULT 'quotation_modern_clean'",
                    "ALTER TABLE free_tool_users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS user_id UUID",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS template_slug TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS document_type TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS document_number TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS business_name TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS business_logo_url TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS business_email TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS business_phone TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS business_address TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS business_tax_number TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS payment_details TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS customer_name TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS customer_email TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS customer_phone TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS customer_address TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS notes TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS due_date DATE",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS valid_until DATE",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS terms TEXT",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS subtotal NUMERIC DEFAULT 0",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS tax NUMERIC DEFAULT 0",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS discount NUMERIC DEFAULT 0",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS total NUMERIC DEFAULT 0",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS watermark BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'draft'",
                    "ALTER TABLE free_tool_documents ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
                    "ALTER TABLE free_tool_document_items ADD COLUMN IF NOT EXISTS document_id UUID",
                    "ALTER TABLE free_tool_document_items ADD COLUMN IF NOT EXISTS item_name TEXT",
                    "ALTER TABLE free_tool_document_items ADD COLUMN IF NOT EXISTS quantity NUMERIC DEFAULT 1",
                    "ALTER TABLE free_tool_document_items ADD COLUMN IF NOT EXISTS unit_price NUMERIC DEFAULT 0",
                    "ALTER TABLE free_tool_document_items ADD COLUMN IF NOT EXISTS total NUMERIC DEFAULT 0",
                    "ALTER TABLE free_tool_document_items ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
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

                # Seed Master Admin
                admin_email = os.getenv("MASTER_ADMIN_EMAIL")
                admin_password = os.getenv("MASTER_ADMIN_PASSWORD")
                if admin_email and admin_password:
                    from werkzeug.security import generate_password_hash
                    cur.execute(
                        """
                        INSERT INTO master_admins (email, password_hash, full_name, role)
                        VALUES (%s, %s, 'Master Admin', 'master_admin')
                        ON CONFLICT (email) DO UPDATE
                        SET password_hash = EXCLUDED.password_hash
                        """,
                        (admin_email, generate_password_hash(admin_password))
                    )
                    print(f"Master Admin setup: {admin_email}")

                # Seed System Settings
                settings = [
                    ("whatsapp_number", "+264812613261"),
                    ("trial_days_default", "14"),
                    ("invoice_free_limit", "2"),
                    ("quotation_free_limit", "2"),
                    ("support_email", "support@vibehost.com"),
                    ("maintenance_message", ""),
                ]
                for key, value in settings:
                    cur.execute(
                        """
                        INSERT INTO system_settings (key, value)
                        VALUES (%s, %s)
                        ON CONFLICT (key) DO NOTHING
                        """,
                        (key, value)
                    )

        print("Schema ensured successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
