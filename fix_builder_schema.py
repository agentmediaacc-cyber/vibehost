import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(".env"))

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

cur.execute("""
ALTER TABLE business_sites
ADD COLUMN IF NOT EXISTS font_style TEXT DEFAULT 'modern',
ADD COLUMN IF NOT EXISTS wallpaper_style TEXT DEFAULT 'premium',
ADD COLUMN IF NOT EXISTS show_services BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS show_gallery BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS show_booking BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS show_whatsapp BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS live_url TEXT;

ALTER TABLE business_profiles
ADD COLUMN IF NOT EXISTS subdomain TEXT UNIQUE,
ADD COLUMN IF NOT EXISTS region TEXT,
ADD COLUMN IF NOT EXISTS town TEXT,
ADD COLUMN IF NOT EXISTS website_type TEXT,
ADD COLUMN IF NOT EXISTS description TEXT;
""")

conn.commit()
cur.close()
conn.close()

print("✅ Builder schema fixed")
