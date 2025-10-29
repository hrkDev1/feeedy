
import feedparser
import aiohttp
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

import db
import user_manager
import utils

logger = logging.getLogger(__name__)

scheduler: Optional[AsyncIOScheduler] = None


async def fetch_feed(feed_url: str, timeout: int = 30) -> Optional[feedparser.FeedParserDict]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    content = await response.text()
                    feed = feedparser.parse(content)
                    
                    if feed.bozo:  
                        logger.warning(f"Feed parsing warning for {feed_url}: {feed.bozo_exception}")
                    
                    return feed
                else:
                    logger.error(f"Failed to fetch {feed_url}: HTTP {response.status}")
                    return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout fetching {feed_url}")
        return None
    except Exception as e:
        logger.error(f"Error fetching {feed_url}: {e}")
        return None


def get_entry_id(entry: Dict) -> str:
    return entry.get("id") or entry.get("link") or entry.get("title", "unknown")


async def get_new_entries(feed_url: str, feed: feedparser.FeedParserDict) -> List[Dict]:

    try:
        last_seen_id = await db.get_last_seen(feed_url)
        
        if not feed.entries:
            return []
        
        new_entries = []
        latest_id = None
        
        for entry in feed.entries:
            entry_id = get_entry_id(entry)
            
            
            if latest_id is None:
                latest_id = entry_id
            
            
            if last_seen_id is None:
                new_entries.append(entry)
                break
            
            
            if entry_id == last_seen_id:
                break
            
            new_entries.append(entry)
        
        
        if latest_id and new_entries:
            await db.update_last_seen(feed_url, latest_id)
        
        return new_entries
    
    except Exception as e:
        logger.error(f"Error processing entries for {feed_url}: {e}")
        return []


async def process_feed(category: str, feed_url: str, bot_instance=None) -> int:
  
    try:
        logger.info(f"Processing feed: {feed_url} ({category})")
        
        feed = await fetch_feed(feed_url)
        if not feed:
            return 0
        
        new_entries = await get_new_entries(feed_url, feed)
        
        if not new_entries:
            logger.debug(f"No new entries for {feed_url}")
            return 0
        
        logger.info(f"Found {len(new_entries)} new entries for {feed_url}")
        
        
        users = await user_manager.get_users_by_category(category)
        
    
        for entry in reversed(new_entries):  
            title = entry.get("title", "No title")
            link = entry.get("link", "")
            summary = utils.clean_html(entry.get("summary", entry.get("description", "")))
            published = entry.get("published", entry.get("updated", ""))
            
            
            thumbnail_url = utils.get_entry_thumbnail(entry)
            
            
            for user in users:
                user_id = user["user_id"]
                
                
                if await user_manager.should_show_post(user_id, title, summary):
                    await db.add_unread_post(
                        uid=user_id,
                        cat=category,
                        title=title,
                        link=link,
                        published=published,
                        summary=summary
                    )
                    
                    
                    await db.trim_unread_posts(user_id, category, limit=10)
            
            
            if bot_instance:
                await post_entry_to_discord(
                    bot=bot_instance,
                    category=category,
                    title=title,
                    link=link,
                    summary=summary,
                    published=published,
                    thumbnail_url=thumbnail_url,
                    users=users
                )
        
        return len(new_entries)
    
    except Exception as e:
        logger.error(f"Error processing feed {feed_url}: {e}")
        return 0


async def post_entry_to_discord(bot, category: str, title: str, link: str, 
                                summary: str, published: str, thumbnail_url: str,
                                users: List[Dict]):
   
    try:
        embed = utils.create_feed_embed(
            title=title,
            link=link,
            description=summary,
            category=category,
            published=published,
            thumbnail_url=thumbnail_url
        )
        
        
        for user in users:
            user_id = user["user_id"]
            
            
            if not await user_manager.should_show_post(user_id, title, summary):
                continue
            
            try:
                discord_user = await bot.fetch_user(user_id)
                await discord_user.send(embed=embed)
                logger.debug(f"Sent post to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send DM to user {user_id}: {e}")
    
    except Exception as e:
        logger.error(f"Error posting to Discord: {e}")


async def check_all_feeds(bot_instance=None):

    try:
        logger.info("Starting feed check cycle")
        
        all_feeds = await db.get_all_feeds()
        total_new = 0
        
        for category, feed_url in all_feeds:
            new_count = await process_feed(category, feed_url, bot_instance)
            total_new += new_count
            
            
            await asyncio.sleep(1)
        
        logger.info(f"Feed check complete. Found {total_new} new entries across all feeds")
        
    except Exception as e:
        logger.error(f"Error in feed check cycle: {e}")


async def initialize_scheduler(bot_instance, check_interval: int = 15):

    global scheduler
    
    try:
        scheduler = AsyncIOScheduler()
        
        
        scheduler.add_job(
            check_all_feeds,
            trigger=IntervalTrigger(minutes=check_interval),
            args=[bot_instance],
            id="feed_checker",
            replace_existing=True,
            max_instances=1
        )
        
        scheduler.start()
        logger.info(f"Scheduler started - checking feeds every {check_interval} minutes")
        
    except Exception as e:
        logger.error(f"Error initializing scheduler: {e}")


async def schedule_daily_summary(bot_instance, hour: int = 9):

    global scheduler
    
    if scheduler is None:
        logger.error("Scheduler not initialized")
        return
    
    try:
        from ai_summary import send_daily_summaries
        
        scheduler.add_job(
            send_daily_summaries,
            trigger=CronTrigger(hour=hour, minute=0),
            args=[bot_instance],
            id="daily_summary",
            replace_existing=True,
            max_instances=1
        )
        
        logger.info(f"Daily summary scheduled for {hour}:00")
    
    except Exception as e:
        logger.error(f"Error scheduling daily summary: {e}")


def stop_scheduler():
   
    global scheduler
    
    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


async def manual_feed_check(category: str = None, feed_url: str = None, bot_instance=None) -> Dict:

    try:
        if feed_url:
            
            if not category:
                
                all_feeds = await db.get_all_feeds()
                for cat, url in all_feeds:
                    if url == feed_url:
                        category = cat
                        break
                
                if not category:
                    return {"error": "Feed URL not found"}
            
            new_count = await process_feed(category, feed_url, bot_instance)
            return {
                "success": True,
                "category": category,
                "feed_url": feed_url,
                "new_entries": new_count
            }
        
        elif category:
            
            feeds = await db.get_feeds_by_category(category)
            total_new = 0
            
            for feed_url in feeds:
                new_count = await process_feed(category, feed_url, bot_instance)
                total_new += new_count
                await asyncio.sleep(1)
            
            return {
                "success": True,
                "category": category,
                "feeds_checked": len(feeds),
                "new_entries": total_new
            }
        
        else:
            
            await check_all_feeds(bot_instance)
            return {"success": True, "message": "All feeds checked"}
    
    except Exception as e:
        logger.error(f"Error in manual feed check: {e}")
        return {"error": str(e)}


async def send_latest_feed_preview(bot, user_id: int, category: str, feed_url: str) -> bool:

    try:
        logger.info(f"Sending preview from {feed_url} to user {user_id}")
        
        feed = await fetch_feed(feed_url)
        if not feed or not feed.entries:
            logger.warning(f"No entries found in {feed_url}")
            return False
        
        
        entry = feed.entries[0]
        
        title = entry.get("title", "No title")
        link = entry.get("link", "")
        summary = utils.clean_html(entry.get("summary", entry.get("description", "")))
        published = entry.get("published", entry.get("updated", ""))
        thumbnail_url = utils.get_entry_thumbnail(entry)
        
        
        embed = utils.create_feed_embed(
            title=title,
            link=link,
            description=summary,
            category=category,
            published=published,
            thumbnail_url=thumbnail_url
        )
        
    
        embed.set_author(name=f"📰 Latest from {category}")
        
        
        try:
            discord_user = await bot.fetch_user(user_id)
            await discord_user.send(embed=embed)
            logger.info(f"Sent preview to user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send preview to user {user_id}: {e}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending preview from {feed_url}: {e}")
        return False


async def send_category_previews(bot, user_id: int, categories: List[str]) -> int:

    try:
        sent_count = 0
        
        for category in categories:
            feeds = await db.get_feeds_by_category(category)
            
            for feed_url in feeds:
                success = await send_latest_feed_preview(bot, user_id, category, feed_url)
                if success:
                    sent_count += 1
                
                
                await asyncio.sleep(0.5)
        
        logger.info(f"Sent {sent_count} previews to user {user_id}")
        return sent_count
    
    except Exception as e:
        logger.error(f"Error sending category previews: {e}")
        return 0


async def validate_feed_url(feed_url: str) -> Tuple[bool, str]:

    try:
        if not utils.is_valid_url(feed_url):
            return False, "Invalid URL format"
        
        feed = await fetch_feed(feed_url)
        
        if feed is None:
            return False, "Could not fetch feed"
        
        if not hasattr(feed, 'entries'):
            return False, "Invalid feed format"
        
        if len(feed.entries) == 0:
            return False, "Feed has no entries"
        
        feed_title = feed.feed.get('title', 'Unknown')
        return True, f"Valid feed: {feed_title}"
    
    except Exception as e:
        return False, f"Error: {str(e)}"


async def populate_initial_posts(bot_instance=None):

    try:
        logger.info("Populating initial posts for all users...")
        
        
        all_feeds = await db.get_all_feeds()
        
        
        feeds_by_cat = {}
        for feed_info in all_feeds:
            cat = feed_info[0]  
            url = feed_info[1]
            if cat not in feeds_by_cat:
                feeds_by_cat[cat] = []
            feeds_by_cat[cat].append(url)
        
        total_posts = 0
        
        
        for cat, feed_urls in feeds_by_cat.items():
            users = await user_manager.get_users_by_cat(cat)
            if not users:
                continue
            
            for url in feed_urls:
                try:
                    feed = await fetch_feed(url)
                    if not feed or not feed.entries:
                        continue
                    
                    
                    entries = feed.entries[:10]
                    
                    for ent in entries:
                        title = ent.get("title", "No title")
                        link = ent.get("link", "")
                        summary = utils.clean_html(ent.get("summary", ent.get("description", "")))
                        published = ent.get("published", ent.get("updated", ""))
                        
                        
                        for user in users:
                            uid = user["user_id"]
                            
                            if await user_manager.should_show_post(uid, title, summary):
                                await db.add_unread_post(
                                    uid=uid,
                                    cat=cat,
                                    title=title,
                                    link=link,
                                    published=published,
                                    summary=summary
                                )
                                total_posts += 1
                        
                        
                        for user in users:
                            await db.trim_unread_posts(user["user_id"], cat, limit=10)
                
                except Exception as e:
                    logger.error(f"Error populating from {url}: {e}")
                    continue
        
        logger.info(f"Initial population complete. Added {total_posts} posts.")
        return total_posts
        
    except Exception as e:
        logger.error(f"Error in populate_initial_posts: {e}")
        return 0
