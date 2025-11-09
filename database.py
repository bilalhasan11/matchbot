import os
from urllib.parse import urlparse
import psycopg
from psycopg.rows import dict_row

DB_URL = os.getenv('SUPABASE_DB_URL')

def get_connection():
    if not DB_URL:
        raise ValueError("SUPABASE_DB_URL not set")
    return psycopg.connect(DB_URL, row_factory=dict_row)

def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    name TEXT,
                    age INTEGER,
                    gender TEXT,
                    looking_for TEXT,
                    city TEXT,
                    bio TEXT,
                    photos TEXT
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS likes (
                    from_id BIGINT,
                    to_id BIGINT,
                    PRIMARY KEY (from_id, to_id)
                )
            ''')
        conn.commit()

def save_profile(user_id, name, age, gender, looking_for, city, bio, photos_paths):
    with get_connection() as conn:
        with conn.cursor() as cur:
            photos_str = ','.join(photos_paths) if photos_paths else ''
            cur.execute('''
                INSERT INTO users (user_id, name, age, gender, looking_for, city, bio, photos)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                name = EXCLUDED.name, age = EXCLUDED.age, gender = EXCLUDED.gender,
                looking_for = EXCLUDED.looking_for, city = EXCLUDED.city,
                bio = EXCLUDED.bio, photos = EXCLUDED.photos
            ''', (user_id, name, age, gender, looking_for, city, bio, photos_str))
        conn.commit()

def get_profile(user_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
            row = cur.fetchone()
            if row:
                row['photos'] = row['photos'].split(',') if row['photos'] else []
                return dict(row)
    return None

def get_candidates(user_id):
    profile = get_profile(user_id)
    if not profile:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT user_id FROM users
                WHERE gender = %s AND user_id != %s AND city ILIKE %s
                ORDER BY RANDOM() LIMIT 10
            ''', (profile['looking_for'], user_id, f"%{profile['city']}%"))
            return [row[0] for row in cur.fetchall()]

def add_like(from_id, to_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO likes (from_id, to_id) VALUES (%s, %s) ON CONFLICT DO NOTHING', (from_id, to_id))
            cur.execute('SELECT 1 FROM likes WHERE from_id = %s AND to_id = %s', (to_id, from_id))
            mutual = cur.fetchone() is not None
        conn.commit()
        return mutual

def get_matches(user_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT u.* FROM users u
                JOIN likes l ON u.user_id = l.from_id
                WHERE l.to_id = %s AND EXISTS (
                    SELECT 1 FROM likes l2 WHERE l2.from_id = %s AND l2.to_id = u.user_id
                )
            ''', (user_id, user_id))
            matches = [dict(row) for row in cur.fetchall()]
            for m in matches:
                m['photos'] = m['photos'].split(',') if m['photos'] else []
            return matches

def download_photo(bot, photo_file, user_id):
    import os
    file = bot.get_file(photo_file.file_id)
    os.makedirs('/tmp/photos', exist_ok=True)
    photo_path = f"/tmp/photos/{user_id}_{photo_file.file_id}.jpg"
    file.download(photo_path)
    return photo_path
