
import aiosqlite
import json
import logging
import aiosqlite
import json
import logging
from datetime import datetime

log = logging.getLogger(__name__)

DB_PATH = "feedybot.db"


async def init_db():
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Users table - stores user subscriptions
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                uid INTEGER PRIMARY KEY,
                uname TEXT NOT NULL,
                cats TEXT NOT NULL,
                keywords TEXT DEFAULT '[]',
                created_at TEXT NOT NULL
            )
        """)
        
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cat TEXT NOT NULL,
                url TEXT NOT NULL,
                added_at TEXT NOT NULL,
                UNIQUE(cat, url),
                FOREIGN KEY (cat) REFERENCES categories(cat) ON DELETE CASCADE
            )
        """)
        
    
        await db.execute("""
            CREATE TABLE IF NOT EXISTS last_seen (
                url TEXT PRIMARY KEY,
                last_entry_id TEXT NOT NULL,
                last_checked TEXT NOT NULL
            )
        """)
        
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS unread_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid INTEGER NOT NULL,
                cat TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                published TEXT,
                summary TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (uid) REFERENCES users(uid) ON DELETE CASCADE
            )
        """)
        
        await db.commit()
        log.info("Database initialized successfully")




async def add_user(uid, uname, cats = None):
    
    if cats is None:
        cats = []
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users (uid, uname, cats, created_at)
                VALUES (?, ?, ?, ?)
            """, (uid, uname, json.dumps(cats), datetime.utcnow().isoformat()))
            await db.commit()
            return True
    except Exception as e:
        log.error(f"Error adding user {uid}: {e}")
        return False


async def get_user(uid):
   
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users WHERE uid = ?", (uid,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "uid": row["uid"],
                        "uname": row["uname"],
                        "cats": json.loads(row["cats"]),
                        "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
                        "created_at": row["created_at"]
                    }
    except Exception as e:
        log.error(f"Error getting user {uid}: {e}")
    return None


async def update_user_subscriptions(uid, categories):
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE users SET cats = ? WHERE uid = ?
            """, (json.dumps(categories), uid))
            await db.commit()
            return True
    except Exception as e:
        log.error(f"Error updating subscriptions for {uid}: {e}")
        return False


async def add_user_keyword(uid, keyword):
    
    try:
        user = await get_user(uid)
        if not user:
            return False
        
        keywords = user.get("keywords", [])
        if keyword.lower() not in [k.lower() for k in keywords]:
            keywords.append(keyword.lower())
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
                    UPDATE users SET keywords = ? WHERE uid = ?
                """, (json.dumps(keywords), uid))
                await db.commit()
        return True
    except Exception as e:
        log.error(f"Error adding keyword for {uid}: {e}")
        return False


async def get_all_users():
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM users") as cursor:
                rows = await cursor.fetchall()
                return [{
                    "uid": row["uid"],
                    "uname": row["uname"],
                    "cats": json.loads(row["cats"]),
                    "keywords": json.loads(row["keywords"]) if row["keywords"] else []
                } for row in rows]
    except Exception as e:
        log.error(f"Error getting all users: {e}")
        return []




async def add_category(cat):
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR IGNORE INTO categories (cat, created_at)
                VALUES (?, ?)
            """, (cat, datetime.utcnow().isoformat()))
            await db.commit()
            return True
    except Exception as e:
        log.error(f"Error adding category {cat}: {e}")
        return False


async def get_all_categories():
   
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT cat FROM categories ORDER BY cat") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    except Exception as e:
        log.error(f"Error getting categories: {e}")
        return []


async def delete_category(cat):
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM feeds WHERE cat = ?", (cat,))
            await db.execute("DELETE FROM categories WHERE cat = ?", (cat,))
            await db.commit()
            return True
    except Exception as e:
        log.error(f"Error deleting category {cat}: {e}")
        return False




async def add_feed(cat, url):
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Ensure category exists
            await add_category(cat)
            
            await db.execute("""
                INSERT OR IGNORE INTO feeds (cat, url, added_at)
                VALUES (?, ?, ?)
            """, (cat, url, datetime.utcnow().isoformat()))
            await db.commit()
            return True
    except Exception as e:
        log.error(f"Error adding feed {url} to {cat}: {e}")
        return False


async def remove_feed(cat, url):
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                DELETE FROM feeds WHERE cat = ? AND url = ?
            """, (cat, url))
            await db.commit()
            return True
    except Exception as e:
        log.error(f"Error removing feed {url} from {cat}: {e}")
        return False


async def get_feeds_by_category(cat):
   
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT url FROM feeds WHERE cat = ?
            """, (cat,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    except Exception as e:
        log.error(f"Error getting feeds for {cat}: {e}")


        return []


async def get_all_feeds():
  
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT cat, url FROM feeds") as cursor:
                return await cursor.fetchall()
    except Exception as e:
        log.error(f"Error getting all feeds: {e}")
        return []




async def update_last_seen(url, entry_id):
   
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO last_seen (url, last_entry_id, last_checked)
                VALUES (?, ?, ?)
            """, (url, entry_id, datetime.utcnow().isoformat()))
            await db.commit()
            return True
    except Exception as e:
        log.error(f"Error updating last seen for {url}: {e}")
        return False


async def get_last_seen(url):
   
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT last_entry_id FROM last_seen WHERE url = ?
            """, (url,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    except Exception as e:
        log.error(f"Error getting last seen for {url}: {e}")
        return None




async def add_unread_post(uid, cat, title, link, 
                         published = None, summary = None):
  
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO unread_posts (uid, cat, title, link, published, summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (uid, cat, title, link, published, summary, datetime.utcnow().isoformat()))
            await db.commit()
            return True
    except Exception as e:
        log.error(f"Error adding unread post for user {uid}: {e}")
        return False


async def get_unread_posts(uid, limit = 50):
  
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT * FROM unread_posts 
                WHERE uid = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (uid, limit)) as cursor:
                rows = await cursor.fetchall()
                return [{
                    "id": row["id"],
                    "cat": row["cat"],
                    "title": row["title"],
                    "link": row["link"],
                    "published": row["published"],
                    "summary": row["summary"],
                    "created_at": row["created_at"]
                } for row in rows]
    except Exception as e:
        log.error(f"Error getting unread posts for {uid}: {e}")
        return []


async def clear_unread_posts(uid):
   
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM unread_posts WHERE uid = ?", (uid,))
            await db.commit()
            return True
    except Exception as e:
        log.error(f"Error clearing unread posts for {uid}: {e}")
        return False


async def get_unread_count(uid) -> int:
 
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("""
                SELECT COUNT(*) FROM unread_posts WHERE uid = ?
            """, (uid,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
    except Exception as e:
        log.error(f"Error getting unread count for {uid}: {e}")
        return 0


async def trim_unread_posts(uid, cat, limit=10):
   
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Delete older posts beyond the limit
            await db.execute("""
                DELETE FROM unread_posts 
                WHERE uid = ? AND cat = ? 
                AND id NOT IN (
                    SELECT id FROM unread_posts 
                    WHERE uid = ? AND cat = ?
                    ORDER BY created_at DESC 
                    LIMIT ?
                )
            """, (uid, cat, uid, cat, limit))
            await db.commit()
            return True
    except Exception as e:
        log.error(f"Error trimming unread posts for {uid}, {cat}: {e}")
        return False
