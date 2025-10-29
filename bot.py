import discord
from discord import app_commands
from discord.ext import commands
import logging
import os
import json
import asyncio
from dotenv import load_dotenv

import db
import user_manager
import feed_manager
import ai_summary
import utils

load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('feedybot.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


token = os.getenv("DISCORD_TOKEN")
prov = os.getenv("G4F_PROVIDER", "auto")
interval = int(os.getenv("FEED_CHECK_INTERVAL", "15"))
sumhour = int(os.getenv("DAILY_SUMMARY_HOUR", "9"))


f = open("config.json", "r")
cfg = json.load(f)
f.close()


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    """Called when bot is ready"""
    log.info(f"Bot logged in as {bot.user}")
    
    
    await db.init_db()
    log.info("Database initialized")
    
    
    for cat, fds in cfg["default_categories"].items():
        await db.add_category(cat)
        for fd in fds:
            await db.add_feed(cat, fd)
    log.info("Default categories loaded")
    
    
    ai_summary.initialize_g4f(prov)
    log.info("G4F (GPT4Free) initialized - AI summaries enabled!")
    
    
    try:
        synced = await bot.tree.sync()
        log.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")
    
    
    await feed_manager.initialize_scheduler(bot, interval)
    

    await feed_manager.schedule_daily_summary(bot, sumhour)
    

    log.info("Loading initial feed posts...")
    posts_loaded = await feed_manager.populate_initial_posts(bot)
    log.info(f"Loaded {posts_loaded} initial posts")
    
    log.info("FeedyBot AI is ready!")


@bot.tree.command(name="help", description="Show bot commands and help")
async def help_command(interaction):
    """Display help information"""
    embed = utils.create_help_embed()
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="setup", description="Set up your feed subscriptions")
async def setup_command(interaction):
    """Interactive setup for user subscriptions"""
    try:
        await interaction.response.defer(ephemeral=True)
    except discord.errors.NotFound:
        log.warning("Interaction expired before defer - user may have taken too long")
        return
    
    try:
        usr = interaction.user
        
    
        cats = await db.get_all_categories()
        
        if not cats:
            await interaction.followup.send("No categories available! Please ask an admin to add feeds.")
            return
        
    
        usrdata = await db.get_user(usr.id)
        subs = usrdata["cats"] if usrdata else []
        

        view = CategorySelectView(cats, subs, usr)
        
        msg = f"**Select categories you want to subscribe to:**\n\n"
        msg += f"You're currently subscribed to: {', '.join(subs) if subs else 'None'}\n\n"
        msg += "Use the dropdown below to update your subscriptions."
        
        await interaction.followup.send(msg, view=view, ephemeral=True)
    
    except Exception as e:
        log.error(f"Error in setup command: {e}")
        await interaction.followup.send("An error occurred. Please try again.")


@bot.tree.command(name="addcategory", description="Create a new category")
async def addcategory_command(interaction, name: str):
    """Add a new category"""
    await interaction.response.defer()
    
    try:
    
        category_name = utils.sanitize_category_name(name)
        
        if not category_name:
            await interaction.followup.send(
                embed=utils.create_error_embed("Invalid category name!")
            )
            return

        
        exists = await db.category_exists(category_name)
        if exists:
            await interaction.followup.send(
                embed=utils.create_error_embed("Category already exists!")
            )
            return

        success = await db.add_category(category_name)
        
        if success:
            await interaction.followup.send(
                embed=utils.create_success_embed(f"Category '{category_name}' created successfully!")
            )
        else:
            await interaction.followup.send(
                embed=utils.create_error_embed("Failed to create category. It may already exist.")
            )
    
    except Exception as e:
        log.error(f"Error in addcategory command: {e}")
        await interaction.followup.send(
            embed=utils.create_error_embed(f"An error occurred: {str(e)}")
        )


@bot.tree.command(name="addfeed", description="Add an RSS feed to a category")
async def addfeed_command(interaction, category: str, url: str):
    """Add a feed to a category"""
    await interaction.response.defer()
    
    try:
        
        if not utils.is_valid_url(url):
            await interaction.followup.send(
                embed=utils.create_error_embed("Invalid URL format!")
            )
            return
        
        
        is_valid, message = await feed_manager.validate_feed_url(url)
        
        if not is_valid:
            await interaction.followup.send(
                embed=utils.create_error_embed(f"Invalid feed: {message}")
            )
            return
        

        success = await db.add_feed(category, url)
        
        if success:
            await interaction.followup.send(
                embed=utils.create_success_embed(
                    f"✅ Feed added to '{category}'!\n\n"
                    f"**URL:** {url}\n"
                    f"**Status:** {message}"
                )
            )
        else:
            await interaction.followup.send(
                embed=utils.create_error_embed("Failed to add feed. It may already exist.")
            )
    
    except Exception as e:
        log.error(f"Error in addfeed command: {e}")
        await interaction.followup.send(
            embed=utils.create_error_embed(f"An error occurred: {str(e)}")
        )


@bot.tree.command(name="removefeed", description="Remove an RSS feed from a category")
async def removefeed_command(interaction, category: str, url: str):
    """Remove a feed from a category"""
    await interaction.response.defer()
    
    try:
        success = await db.remove_feed(category, url)
        
        if success:
            await interaction.followup.send(
                embed=utils.create_success_embed(f"Feed removed from '{category}'!")
            )
        else:
            await interaction.followup.send(
                embed=utils.create_error_embed("Failed to remove feed.")
            )
    
    except Exception as e:
        log.error(f"Error in removefeed command: {e}")
        await interaction.followup.send(
            embed=utils.create_error_embed(f"An error occurred: {str(e)}")
        )


@bot.tree.command(name="listfeeds", description="List all feeds in a category")
async def listfeeds_command(interaction, category: str):
    """List feeds in a category"""
    await interaction.response.defer()
    
    try:
        feeds = await db.get_feeds_by_category(category)
        
        embed = discord.Embed(
            title=f"📡 Feeds in '{category}'",
            description=utils.format_feed_list(feeds),
            color=utils.get_embed_color()
        )
        
        embed.set_footer(text=f"Total: {len(feeds)} feeds")
        
        await interaction.followup.send(embed=embed)
    
    except Exception as e:
        log.error(f"Error in listfeeds command: {e}")
        await interaction.followup.send(
            embed=utils.create_error_embed(f"An error occurred: {str(e)}")
        )


@bot.tree.command(name="categories", description="List all available categories")
async def categories_command(interaction):
    """List all categories"""
    await interaction.response.defer()
    
    try:
        categories = await db.get_all_categories()
        user_subs = await user_manager.get_user_categories(interaction.user.id)
        
        embed = discord.Embed(
            title="📂 Available Categories",
            description=utils.format_category_list(categories, user_subs),
            color=utils.get_embed_color()
        )
        
        embed.set_footer(text=f"Total: {len(categories)} categories • ✅ = Subscribed")
        
        await interaction.followup.send(embed=embed)
    
    except Exception as e:
        log.error(f"Error in categories command: {e}")
        await interaction.followup.send(
            embed=utils.create_error_embed(f"An error occurred: {str(e)}")
        )


@bot.tree.command(name="myfeeds", description="Show your subscribed feeds")
async def myfeeds_command(interaction):
    """Show user's subscribed feeds"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        feeds = await user_manager.get_user_feeds(interaction.user.id)
        
        if not feeds:
            await interaction.followup.send(
                embed=utils.create_error_embed(
                    "You haven't subscribed to any feeds yet!\n"
                    "Use `/setup` to get started."
                )
            )
            return
        
        embed = discord.Embed(
            title="📰 Your Subscribed Feeds",
            color=utils.get_embed_color()
        )
        
        for category, feed_list in feeds.items():
            embed.add_field(
                name=f"📂 {category}",
                value=f"{len(feed_list)} feeds",
                inline=True
            )
        
        total_feeds = sum(len(f) for f in feeds.values())
        embed.set_footer(text=f"Total: {total_feeds} feeds across {len(feeds)} categories")
        
        await interaction.followup.send(embed=embed)
    
    except Exception as e:
        log.error(f"Error in myfeeds command: {e}")
        await interaction.followup.send(
            embed=utils.create_error_embed(f"An error occurred: {str(e)}")
        )


@bot.tree.command(name="summary", description="Get AI summary of your unread posts")
async def summary_command(interaction):
    """Generate AI summary for user"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        if not await user_manager.is_user_registered(interaction.user.id):
            await interaction.followup.send(
                embed=utils.create_error_embed(
                    "You need to set up your subscriptions first!\n"
                    "Use `/setup` to get started."
                )
            )
            return
        
        success = await ai_summary.send_sum_to_user(
            bot, 
            interaction.user.id, 
            clear_after=True
        )
        
        if success:
            await interaction.followup.send(
                embed=utils.create_success_embed(
                    "✅ Summary sent! Check your DMs.\n"
                    "Your unread posts have been cleared."
                )
            )
        else:
            await interaction.followup.send(
                embed=utils.create_error_embed(
                    "You have no unread posts to summarize!"
                )
            )
    
    except Exception as e:
        log.error(f"Error in summary command: {e}")
        await interaction.followup.send(
            embed=utils.create_error_embed(f"An error occurred: {str(e)}")
        )


@bot.tree.command(name="addkeyword", description="Add keyword filter for posts")
async def addkeyword_command(interaction, keyword: str):
    """Add keyword filter"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        if not await user_manager.is_user_registered(interaction.user.id):
            await interaction.followup.send(
                embed=utils.create_error_embed(
                    "You need to set up your subscriptions first!\n"
                    "Use `/setup` to get started."
                )
            )
            return
        
        success = await user_manager.add_keyword_filter(interaction.user.id, keyword)
        
        if success:
            await interaction.followup.send(
                embed=utils.create_success_embed(
                    f"Keyword '{keyword}' added!\n"
                    f"You'll only see posts containing this keyword."
                )
            )
        else:
            await interaction.followup.send(
                embed=utils.create_error_embed("Failed to add keyword.")
            )
    
    except Exception as e:
        log.error(f"Error in addkeyword command: {e}")
        await interaction.followup.send(
            embed=utils.create_error_embed(f"An error occurred: {str(e)}")
        )


@bot.tree.command(name="stats", description="View your subscription statistics")
async def stats_command(interaction):
    """Show user statistics"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        stats = await user_manager.get_user_stats(interaction.user.id)
        
        if not stats:
            await interaction.followup.send(
                embed=utils.create_error_embed(
                    "You haven't set up your subscriptions yet!\n"
                    "Use `/setup` to get started."
                )
            )
            return
        
        embed = discord.Embed(
            title=f"📊 Statistics for {stats['username']}",
            color=utils.get_embed_color()
        )
        
        embed.add_field(
            name="📂 Categories",
            value=f"{stats['categories_count']} subscribed",
            inline=True
        )
        
        embed.add_field(
            name="📡 Feeds",
            value=f"{stats['feeds_count']} total",
            inline=True
        )
        
        embed.add_field(
            name="📬 Unread Posts",
            value=f"{stats['unread_count']} pending",
            inline=True
        )
        
        if stats['keywords']:
            embed.add_field(
                name="🔑 Keywords",
                value=", ".join(stats['keywords']),
                inline=False
            )
        
        embed.set_footer(text=f"Member since {utils.format_timestamp(stats['created_at'])}")
        
        await interaction.followup.send(embed=embed)
    
    except Exception as e:
        log.error(f"Error in stats command: {e}")
        await interaction.followup.send(
            embed=utils.create_error_embed(f"An error occurred: {str(e)}")
        )


@bot.tree.command(name="checkfeeds", description="Manually trigger feed check (Admin)")
async def checkfeeds_command(interaction):
    """Manually check feeds (admin command)"""
    await interaction.response.defer()
    
    try:

        result = await feed_manager.manual_feed_check(bot_instance=bot)
        
        if result.get("success"):
            await interaction.followup.send(
                embed=utils.create_success_embed(
                    f"✅ Feed check complete!\n"
                    f"{result.get('message', 'All feeds checked.')}"
                )
            )
        else:
            await interaction.followup.send(
                embed=utils.create_error_embed(
                    f"Error: {result.get('error', 'Unknown error')}"
                )
            )
    
    except Exception as e:
        log.error(f"Error in checkfeeds command: {e}")
        await interaction.followup.send(
            embed=utils.create_error_embed(f"An error occurred: {str(e)}")
        )


class CategorySelectView(discord.ui.View):
    def __init__(self, categories, current_subs, user):
        super().__init__(timeout=300)  
        self.categories = categories
        self.current_subs = current_subs
        self.user = user
        
        
        self.add_item(CategorySelect(categories, current_subs))


class CategorySelect(discord.ui.Select):
    def __init__(self, categories, current_subs):
        options = [
            discord.SelectOption(
                label=category,
                description=f"{'✅ Subscribed' if category in current_subs else 'Not subscribed'}",
                default=category in current_subs
            )
            for category in categories
        ]
        
        super().__init__(
            placeholder="Select categories to subscribe...",
            min_values=0,
            max_values=len(categories),
            options=options
        )
    
    async def callback(self, interaction):
        try:
            selected = self.values
            
            
            success = await user_manager.setup_user(
                interaction.user.id,
                str(interaction.user),
                selected
            )
            
            if success:
                embed = utils.create_success_embed(
                    f"✅ Subscriptions updated!\n\n"
                    f"**Subscribed to:** {len(selected)} categories\n"
                    f"{', '.join(selected) if selected else 'None'}\n\n"
                    f"📬 Sending the latest posts to your DMs..."
                )
                await interaction.response.edit_message(embed=embed, view=None)
                
                
                if selected:
                    
                    bot_instance = interaction.client
                    uid = interaction.user.id
                    
                    
                    async def send_previews():
                        try:
                            previews_sent = await feed_manager.send_category_previews(
                                bot_instance,
                                uid,
                                selected
                            )
                            log.info(f"Sent {previews_sent} preview posts to user {uid}")
                        except Exception as e:
                            log.error(f"Error sending previews: {e}")
                    
                    
                    asyncio.create_task(send_previews())
            else:
                embed = utils.create_error_embed("Failed to update subscriptions.")
                await interaction.response.edit_message(embed=embed, view=None)
        
        except Exception as e:
            log.error(f"Error in category select callback: {e}")
            try:
                await interaction.response.send_message(
                    embed=utils.create_error_embed(f"An error occurred: {str(e)}"),
                    ephemeral=True
                )
            except:
                await interaction.followup.send(
                    embed=utils.create_error_embed(f"An error occurred: {str(e)}"),
                    ephemeral=True
                )


def main():
    if not token:
        log.error("No Discord token found! Set token in .env file")
        return
    
    try:
        bot.run(token)
    except Exception as e:
        log.error(f"Failed to start bot: {e}")
    finally:
        feed_manager.stop_scheduler()


if __name__ == "__main__":
    main()
