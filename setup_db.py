from dotenv import load_dotenv
from pathlib import Path
import os
import psycopg2

load_dotenv(dotenv_path=Path(".env"))

DATABASE_URL = os.getenv("DATABASE_URL")

print("🔌 Connecting to Neon...")

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("✅ Connected\n")

schema = """

CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS businesses (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    owner_id UUID,
    business_name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    category TEXT,
    phone TEXT,
    whatsapp TEXT,
    email TEXT,
    logo_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS business_sites (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    business_id UUID,
    site_title TEXT,
    template_name TEXT DEFAULT 'modern',
    primary_color TEXT DEFAULT '#111827',
    secondary_color TEXT DEFAULT '#d4af37',
    accent_color TEXT DEFAULT '#ff6b6b',
    hero_title TEXT,
    hero_subtitle TEXT,
    background_image TEXT,
    published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS site_services (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    business_id UUID,
    service_name TEXT,
    description TEXT,
    price TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS site_gallery (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    business_id UUID,
    image_url TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    business_id UUID,
    plan_name TEXT DEFAULT 'starter',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);

"""

cur.execute(schema)

conn.commit()

print("✅ VibeHost tables created successfully")

cur.close()
conn.close()

print("✅ Database setup complete")
