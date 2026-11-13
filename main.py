"""Entry point — boots db, deriver, cogs, and the deposit monitor."""
import asyncio
import logging
import os
import re

import discord
from discord.ext import commands

from config import Config
from database import Database
from functions.deposit import DepositMonitor
from functions.wallet import WalletDeriver
from functions import utils

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger("bot")

COGS = (
    "functions.economy",
    "functions.deposit",
    "functions.coinflip",
    "functions.crash",
    "functions.horse",
    "functions.limbo",
    "functions.hilo",
    "functions.plinko",
    "functions.towers",
    "functions.keno",
    "functions.blackjack",
    "functions.baccarat",
    "functions.mines",
    "functions.stats",
    "functions.threads",
    "functions.admin",
    "functions.help",
    "functions.moderation",
)

class GamblingBot(commands.Bot):
    def __init__(self, db: Database, deriver: WalletDeriver | None):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix=commands.when_mentioned_or(Config.PREFIX),
            intents=intents, help_command=None, case_insensitive=True,
        )
        self.db = db
        self.deriver = deriver
        self.monitor: DepositMonitor | None = None

    async def setup_hook(self):
        for ext in COGS:
            await self.load_extension(ext)
            log.info("loaded %s", ext)

        self.monitor = DepositMonitor(self)
        await self.tree.sync()
        log.info("application commands synced")

    async def on_ready(self):
        log.info("logged in as %s (%s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name=f"{Config.PREFIX}help"
            )
        )

    async def close(self):
        await self.db.close()
        await super().close()

async def main():
    if not Config.TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set")
    os.makedirs(os.path.dirname(Config.DB_PATH) or ".", exist_ok=True)

    db = Database(Config.DB_PATH)
    await db.init()
    log.info("database ready at %s", Config.DB_PATH)

    deriver = None
    if Config.MASTER_MNEMONIC:
        deriver = WalletDeriver(Config.MASTER_MNEMONIC)
        log.info("HD deriver ready")

    bot = GamblingBot(db, deriver)

    @bot.event
    async def on_message(message):
        if message.author.bot:
            return

        # 1. Check if user is banned from the casino
        if await bot.db.is_user_banned(message.author.id):
            return

        content = message.content
        if content.startswith(Config.PREFIX):
            content = re.sub(rf"^\{Config.PREFIX}\s+", Config.PREFIX, content)
            
            parts = content.split()
            if len(parts) >= 3 and parts[0].lower() in [f"{Config.PREFIX}cf", f"{Config.PREFIX}coinflip"]:
                if parts[1].isdigit() and parts[2].lower() in ['h', 't', 'heads', 'tails']:
                    parts[1], parts[2] = parts[2], parts[1]
                    content = " ".join(parts)

            # 2. First time registration check
            user = await bot.db.get_user(message.author.id)
            if not user:
                await bot.db.get_or_create_user(message.author.id)
                
                e = utils.ok(
                    "First time registration",
                    "You have been automatically registered in the system!"
                )
                e.set_footer(text="The Godfather", icon_url="https://files.catbox.moe/jeph3g.jpg")
                
                welcome_text = "-# Welcome to The Godfather Casino"
                await message.channel.send(content=welcome_text, embed=e)

            # Discord.py requires a proxy message to change content securely
            class MessageProxy:
                def __init__(self, original, new_content):
                    self._original = original
                    self.content = new_content
                def __getattr__(self, item):
                    return getattr(self._original, item)

            message = MessageProxy(message, content)

        await bot.process_commands(message)

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            e = discord.Embed(
                title="❌ Missing Input",
                description=f"You are missing the `{error.param.name}` argument.\n\n"
                            f"**Usage:** `{Config.PREFIX}{ctx.command.name} {ctx.command.signature}`",
                color=0xDA373C
            )
            await ctx.send(embed=e)
        elif isinstance(error, commands.BadArgument):
            e = discord.Embed(
                title="❌ Invalid Input",
                description=f"The input provided was invalid (e.g., typing letters instead of numbers).\n\n"
                            f"**Usage:** `{Config.PREFIX}{ctx.command.name} {ctx.command.signature}`",
                color=0xDA373C
            )
            await ctx.send(embed=e)
        else:
            log.error("Unhandled command error", exc_info=error)

    try:
        await bot.start(Config.TOKEN)
    finally:
        await db.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass