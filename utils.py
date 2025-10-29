
import re
import json
import logging

from datetime import datetime
from urllib.parse import urlparse
import discord

log = logging.getLogger(__name__)


try:
    with open("config.json", "r") as f:
        CONFIG = json.load(f)
except Exception as e:
    log.warning(f"Could not load config.json: {e}")
    CONFIG = {
        "embed_color": "0x3498db",
        "post_description_length": 200
    }


def get_embed_color() -> int:
    """Get the embed color from config"""
    try:
        color_str = CONFIG.get("embed_color", "0x3498db")
        return int(color_str, 16)
    except:
        return 0x3498db  


def clean_html(text) -> str:

    if not text:
        return ""

    text = re.sub(r'<[^>]+>', '', text)
    

    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&nbsp;', ' ')
    
  
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def truncate_text(text, max_length=200) -> str:
 
    if not text:
        return ""
    
    text = clean_html(text)
    
    if len(text) <= max_length:
        return text
   
    return text[:max_length-3].rstrip() + "..."


def format_timestamp(timestamp_str) -> str:
  
    if not timestamp_str:
        return "Unknown date"
    
    try:
       
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except:
        pass
    
    try:
       
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(timestamp_str)
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except:
        pass
    
   
    return timestamp_str


def is_valid_url(url):

    if not url:
        return False
    
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except:
        return False


def get_entry_thumbnail(entry):
  
    try:
       
        if hasattr(entry, 'media_content'):
            for media in entry.media_content:
                if 'url' in media:
                    return media['url']
        
        
        if hasattr(entry, 'media_thumbnail'):
            if entry.media_thumbnail and len(entry.media_thumbnail) > 0:
                return entry.media_thumbnail[0].get('url')
        
        
        if hasattr(entry, 'enclosures'):
            for enclosure in entry.enclosures:
                if enclosure.get('type', '').startswith('image/'):
                    return enclosure.get('href')
        
       
        if hasattr(entry, 'links'):
            for link in entry.links:
                if link.get('rel') == 'enclosure' or link.get('type', '').startswith('image/'):
                    return link.get('href')
      
        content = entry.get('summary', '') or entry.get('description', '')
        if content:
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
            if img_match:
                return img_match.group(1)
    
    except Exception as e:
        log.debug(f"Error extracting thumbnail: {e}")
    
    return None


def create_feed_embed(title, link, description, 
                     category, published=None, 
                     thumbnail_url=None) -> discord.Embed:

    max_desc_length = CONFIG.get("post_description_length", 200)
    
    embed = discord.Embed(
        title=truncate_text(title, 256),
        url=link,
        description=truncate_text(description, max_desc_length),
        color=get_embed_color(),
        timestamp=datetime.utcnow()
    )
  
    embed.add_field(name="Category", value=category, inline=True)
    
  
    if published:
        formatted_date = format_timestamp(published)
        embed.add_field(name="Published", value=formatted_date, inline=True)
    

    if thumbnail_url and is_valid_url(thumbnail_url):
        embed.set_thumbnail(url=thumbnail_url)
    
 
    embed.set_footer(text="FeedyBot AI • RSS Feed Update")
    
    return embed


def create_summary_embed(summary, total_posts, 
                        categories) -> discord.Embed:
  
    embed = discord.Embed(
        title="📰 Your Daily Feed Summary",
        description=summary[:4000],  
        color=get_embed_color(),
        timestamp=datetime.utcnow()
    )
    
    
    embed.add_field(
        name="📊 Statistics",
        value=f"**Total Posts:** {total_posts}\n**Categories:** {len(categories)}",
        inline=False
    )
    

    if categories:
        category_text = "\n".join([f"• {cat}: {count}" for cat, count in categories.items()])
        embed.add_field(
            name="📂 By Category",
            value=category_text[:1024], 
            inline=False
        )
    
    embed.set_footer(text="FeedyBot AI • Powered by GPT4Free (g4f)")
    
    return embed


def create_info_embed(title, description, 
                     fields = None,
                     color="blue") -> discord.Embed:
   
    color_map = {
        "blue": 0x3498db,
        "green": 0x2ecc71,
        "red": 0xe74c3c,
        "yellow": 0xf39c12,
        "purple": 0x9b59b6
    }
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=color_map.get(color, get_embed_color()),
        timestamp=datetime.utcnow()
    )
    
    if fields:
        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=False)
    
    embed.set_footer(text="FeedyBot AI")
    
    return embed


def create_error_embed(error_message) -> discord.Embed:

    return create_info_embed(
        title="❌ Error",
        description=error_message,
        color="red"
    )


def create_success_embed(message) -> discord.Embed:

    return create_info_embed(
        title="✅ Success",
        description=message,
        color="green"
    )


def create_help_embed() -> discord.Embed:

    embed = discord.Embed(
        title="🤖 FeedyBot AI - Help",
        description="Stay updated with RSS feeds and AI-powered summaries!",
        color=get_embed_color(),
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(
        name="📝 Setup Commands",
        value=(
            "`/setup` - Configure your feed subscriptions\n"
            "`/addcategory <name>` - Create a custom category\n"
            "`/addfeed <category> <url>` - Add RSS feed to category\n"
            "`/removefeed <category> <url>` - Remove feed from category"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📊 Information Commands",
        value=(
            "`/listfeeds <category>` - List all feeds in a category\n"
            "`/myfeeds` - Show your subscribed feeds\n"
            "`/categories` - List all available categories"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🤖 AI Commands",
        value=(
            "`/summary` - Get AI summary of your unread posts\n"
            "`/addkeyword <word>` - Filter posts by keyword"
        ),
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ Other",
        value=(
            "`/help` - Show this help message\n"
            "`/stats` - View your subscription statistics"
        ),
        inline=False
    )
    
    embed.set_footer(text="FeedyBot AI • Powered by GPT4Free (g4f)")
    
    return embed


def format_category_list(categories: list, subscribed: list = None) -> str:

    if not categories:
        return "No categories available."
    
    lines = []
    for category in sorted(categories):
        if subscribed and category in subscribed:
            lines.append(f"✅ **{category}**")
        else:
            lines.append(f"⬜ {category}")
    
    return "\n".join(lines)


def format_feed_list(feeds: list, max_display=10) -> str:

    if not feeds:
        return "No feeds in this category."
    
    lines = []
    for i, feed in enumerate(feeds[:max_display], 1):
        lines.append(f"{i}. {feed}")
    
    if len(feeds) > max_display:
        lines.append(f"\n... and {len(feeds) - max_display} more")
    
    return "\n".join(lines)


def sanitize_category_name(name) -> str:

    name = re.sub(r'[^a-zA-Z0-9\s&-]', '', name)
    
    name = ' '.join(name.split())
    
    return name.strip()
