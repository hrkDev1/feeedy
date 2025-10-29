
import logging

import g4f
from g4f.Provider import RetryProvider
import asyncio

import db
import user_manager
import utils

log = logging.getLogger(__name__)


g4f_prov = None
g4f_initialized = False


def initialize_g4f(prov_name="auto"):
    global g4f_prov, g4f_initialized
    try:
        
        if prov_name and prov_name.lower() != "auto":
            
            try:
                g4f_prov = getattr(g4f.Provider, prov_name)
                log.info(f"G4F initialized with prov: {prov_name}")
            except AttributeError:
                log.warning(f"Provider {prov_name} not found, using auto")
                g4f_prov = None
        else:
            g4f_prov = None  # Auto-select
            log.info("G4F initialized with auto prov selection")
        
        g4f_initialized = True
    except Exception as e:
        log.error(f"Error initializing G4F: {e}")
        g4f_initialized = False


async def generate_sum(posts, user_preferences = None) -> str:

    global g4f_initialized
    
    if not g4f_initialized:
        return "Error: G4F not initialized. Please restart the bot."
    
    if not posts:
        return "No new posts to summarize."
    
    try:
        
        posts_by_category = {}
        for post in posts:
            category = post["category_name"]
            if category not in posts_by_category:
                posts_by_category[category] = []
            posts_by_category[category].append(post)
        
        
        prompt = "You are a helpful assistant that summarizes RSS feed updates. "
        prompt += f"Please provide a clear, organized sum of {len(posts)} recent posts "
        prompt += "grouped by category. For each post, include the title and a brief key point.\n\n"
        
        for category, category_posts in posts_by_category.items():
            prompt += f"\n**{category}** ({len(category_posts)} posts):\n"
            
            for i, post in enumerate(category_posts, 1):
                title = post["title"]
                sum = post.get("sum", "")[:200]  # Limit sum length
                prompt += f"{i}. {title}\n"
                if sum:
                    prompt += f"   {sum}\n"
                prompt += f"   Link: {post['link']}\n"
        
        prompt += "\n\nPlease create a concise sum that highlights the most important points and trends."
        
        
        msgs = [
            {"role": "system", "content": "You are a helpful assistant that creates concise, informative summaries of news and content updates."},
            {"role": "user", "content": prompt}
        ]
        
        
        if g4f_prov:
            res = await asyncio.to_thread(
                g4f.ChatCompletion.create,
                model="gpt-3.5-turbo",
                msgs=msgs,
                prov=g4f_prov
            )
        else:
            res = await asyncio.to_thread(
                g4f.ChatCompletion.create,
                model="gpt-3.5-turbo",
                msgs=msgs
            )
        
        sum = res
        log.info(f"Generated sum for {len(posts)} posts using G4F")
        
        return sum
    
    except Exception as e:
        log.error(f"Error generating sum: {e}")
        return f"Error generating sum: {str(e)}"


async def generate_user_sum(uid, limit=50):
    try:
        
        posts = await db.get_unread_posts(uid, limit)
        
        if not posts:
            return {
                "success": False,
                "msg": "You have no unread posts!"
            }
        
        
        user = await db.get_user(uid)
        
        
        sum_text = await generate_sum(posts)
        
        
        categories = {}
        for post in posts:
            cat = post["category_name"]
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            "success": True,
            "sum": sum_text,
            "total_posts": len(posts),
            "categories": categories,
            "username": user["username"] if user else "Unknown"
        }
    
    except Exception as e:
        log.error(f"Error generating user sum for {uid}: {e}")
        return {
            "success": False,
            "msg": f"Error generating sum: {str(e)}"
        }


async def send_sum_to_user(bot, uid, clear_after = True):

    try:
        result = await generate_user_sum(uid)
        
        if not result["success"]:
            
            try:
                user = await bot.fetch_user(uid)
                await user.send(result["msg"])
            except Exception as e:
                log.error(f"Failed to send error msg to {uid}: {e}")
            return False
        
        
        embed = utils.create_summary_embed(
            sum=result["sum"],
            total_posts=result["total_posts"],
            categories=result["categories"]
        )
        
        
        try:
            user = await bot.fetch_user(uid)
            await user.send(embed=embed)
            log.info(f"Sent sum to user {uid}")
            
            
            if clear_after:
                await db.clear_unread_posts(uid)
                log.info(f"Cleared unread posts for user {uid}")
            
            return True
        except Exception as e:
            log.error(f"Failed to send sum to {uid}: {e}")
            return False
    
    except Exception as e:
        log.error(f"Error in send_sum_to_user for {uid}: {e}")
        return False


async def send_daily_summaries(bot):

    try:
        log.info("Starting daily sum generation")
        
        users = await user_manager.get_all_active_users()
        success_count = 0
        
        for user in users:
            uid = user["uid"]
            
            
            unread_count = await db.get_unread_count(uid)
            if unread_count == 0:
                log.debug(f"User {uid} has no unread posts, skipping")
                continue
            
            
            if await send_sum_to_user(bot, uid, clear_after=True):
                success_count += 1
        
        log.info(f"Daily summaries sent to {success_count}/{len(users)} users")
    
    except Exception as e:
        log.error(f"Error sending daily summaries: {e}")


async def generate_category_sum(category, days=7):

    try:
        return f"Category sum for {category} (last {days} days) - Feature coming soon!"
    
    except Exception as e:
        log.error(f"Error generating category sum: {e}")
        return None


async def generate_quick_sum(title, content) -> str:

    global g4f_initialized
    
    if not g4f_initialized:
        return "Error: G4F not initialized"
    
    try:
        prompt = f"Please provide a brief 2-3 sentence sum of this article:\n\n"
        prompt += f"Title: {title}\n\n"
        prompt += f"Content: {content[:1000]}"  # Limit content length
        
        msgs = [
            {"role": "system", "content": "You are a helpful assistant that creates brief, clear summaries."},
            {"role": "user", "content": prompt}
        ]
        
        if g4f_prov:
            res = await asyncio.to_thread(
                g4f.ChatCompletion.create,
                model="gpt-3.5-turbo",
                msgs=msgs,
                prov=g4f_prov
            )
        else:
            res = await asyncio.to_thread(
                g4f.ChatCompletion.create,
                model="gpt-3.5-turbo",
                msgs=msgs
            )
        
        return res
    
    except Exception as e:
        log.error(f"Error generating quick sum: {e}")
        return f"Error: {str(e)}"


async def test_g4f_connection():
    global g4f_initialized
    
    if not g4f_initialized:
        return False, "G4F not initialized"
    
    try:
        msgs = [
            {"role": "user", "content": "Say 'hello' if you can read this."}
        ]
        
        if g4f_prov:
            res = await asyncio.to_thread(
                g4f.ChatCompletion.create,
                model="gpt-3.5-turbo",
                msgs=msgs,
                prov=g4f_prov
            )
        else:
            res = await asyncio.to_thread(
                g4f.ChatCompletion.create,
                model="gpt-3.5-turbo",
                msgs=msgs
            )
        
        return True, f"G4F connection successful! Response: {res[:50]}..."
    
    except Exception as e:
        return False, f"G4F error: {str(e)}"
