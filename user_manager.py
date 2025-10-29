
import logging

import db

log = logging.getLogger(__name__)


async def setup_user(uid, uname, cats):
    try:
        
        user = await db.get_user(uid)
        
        if user:
            
            success = await db.update_user_subscriptions(uid, cats)
        else:
            
            success = await db.add_user(uid, uname, cats)
        
        if success:
            log.info(f"User {uname} ({uid}) subscribed to: {', '.join(cats)}")
        
        return success
    except Exception as e:
        log.error(f"Error setting up user {uid}: {e}")
        return False


async def add_cat_to_user(uid, cat):
  
    try:
        user = await db.get_user(uid)
        if not user:
            return False
        
        cats = user["subscribed_cats"]
        if cat not in cats:
            cats.append(cat)
            return await db.update_user_subscriptions(uid, cats)
        
        return True  
    except Exception as e:
        log.error(f"Error adding cat for user {uid}: {e}")
        return False


async def remove_cat_from_user(uid, cat):
   
    try:
        user = await db.get_user(uid)
        if not user:
            return False
        
        cats = user["subscribed_cats"]
        if cat in cats:
            cats.remove(cat)
            return await db.update_user_subscriptions(uid, cats)
        
        return True  
    except Exception as e:
        log.error(f"Error removing cat for user {uid}: {e}")
        return False


async def get_user_cats(uid):
   
    try:
        user = await db.get_user(uid)
        return user["subscribed_cats"] if user else []
    except Exception as e:
        log.error(f"Error getting cats for user {uid}: {e}")
        return []


async def get_user_feeds(uid):

    try:
        cats = await get_user_cats(uid)
        feeds = {}
        
        for cat in cats:
            cat_feeds = await db.get_feeds_by_cat(cat)
            if cat_feeds:
                feeds[cat] = cat_feeds
        
        return feeds
    except Exception as e:
        log.error(f"Error getting feeds for user {uid}: {e}")
        return {}


async def get_users_by_cat(cat):
   
    try:
        all_users = await db.get_all_users()
        return [
            user for user in all_users 
            if cat in user["subscribed_cats"]
        ]
    except Exception as e:
        log.error(f"Error getting users for cat {cat}: {e}")
        return []


async def add_keyword_filter(uid, keyword):
   
    try:
        return await db.add_user_keyword(uid, keyword)
    except Exception as e:
        log.error(f"Error adding keyword filter for user {uid}: {e}")
        return False


async def get_user_keywords(uid):
 
    try:
        user = await db.get_user(uid)
        return user["keywords"] if user else []
    except Exception as e:
        log.error(f"Error getting keywords for user {uid}: {e}")
        return []


async def should_show_post(uid, title, summary=""):

    try:
        keywords = await get_user_keywords(uid)
        
        
        if not keywords:
            return True
        
        
        content = f"{title} {summary}".lower()
        return any(keyword.lower() in content for keyword in keywords)
    
    except Exception as e:
        log.error(f"Error checking post filter for user {uid}: {e}")
        return True  


async def get_user_stats(uid):
   
    try:
        user = await db.get_user(uid)
        if not user:
            return {}
        
        cats = user["subscribed_cats"]
        feeds = await get_user_feeds(uid)
        total_feeds = sum(len(feed_list) for feed_list in feeds.values())
        unread_count = await db.get_unread_count(uid)
        keywords = user["keywords"]
        
        return {
            "uname": user["uname"],
            "cats_count": len(cats),
            "cats": cats,
            "feeds_count": total_feeds,
            "unread_count": unread_count,
            "keywords_count": len(keywords),
            "keywords": keywords,
            "created_at": user["created_at"]
        }
    except Exception as e:
        log.error(f"Error getting stats for user {uid}: {e}")
        return {}


async def is_user_registered(uid):
   
    user = await db.get_user(uid)
    return user is not None


async def get_all_active_users():
    try:
        all_users = await db.get_all_users()
        return [
            user for user in all_users 
            if len(user["subscribed_cats"]) > 0
        ]
    except Exception as e:
        log.error(f"Error getting active users: {e}")
        return []
