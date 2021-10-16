'''
Veron1CA
Licensed under MIT; Copyright 2021 HitBlast
'''


# Import built-in libraries.
import os
import sys
import time
import math
import uvloop
import random
import asyncio
import datetime
import functools
import itertools
import traceback
from threading import Thread

# Import third-party libraries.
import git
import topgg
import qrcode
import youtube_dl
from flask import Flask
from tinydb import TinyDB, Query
from async_timeout import timeout
from better_profanity import profanity
from decouple import config, UndefinedValueError

# Import the API wrapper and its components.
import disnake
from disnake.ext import commands
from disnake import Option, OptionType
from disnake.interactions.application_command import ApplicationCommandInteraction


# Environment variables.
try:
    token = config('TOKEN', cast=str)
    dbl_token = config('DBL_TOKEN', default=None, cast=str)
    owner = config('OWNER_ID', cast=int)
    prefix = config('COMMAND_PREFIX', default='vrn.', cast=str)

except UndefinedValueError:
    print('One or more secrets have been left undefined. Consider going through the README.md file for proper instructions on setting Veron1CA up.')
    time.sleep(5)
    exit()


# System variables and objects.
accent_color = [11977158, 14573921]
lock_roles = ['BotMod', 'BotAdmin']
last_restarted_str = str(datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
last_restarted_obj = time.time()

# The guild / server database.
db = TinyDB('guild-db.json')
Guild = Query()

# Loading the word list for the swear filter.
profanity.load_censor_words_from_file('filtered.txt')

# Global variables.
global jail_members
jail_members = list()
global frozen_guilds
frozen_guilds = list()
global msg_web_target
msg_web_target = list()
global msg_web_records
msg_web_records = list()
global snipeables
snipeables = list()


# Get prefix by guild ID.
def get_prefix(bot: commands.AutoShardedBot, message: disnake.Message):
    guild_prefix = prefix

    try:
        for guild in db.all():
            if guild['id'] == message.guild.id: 
                if guild['prefix']:
                    guild_prefix = guild['prefix']
    except AttributeError:
        pass

    return commands.when_mentioned_or(guild_prefix)(bot, message)


# Standard Functions.
def get_guild_dict(guild_id: int):
    guild = db.search(Guild.id == guild_id)
    return guild[0] if guild else None

def generate_random_footer():
    footers_list = [
        'Hey there pal :D',
        'Hey! Want some pants?',
        'When pigs fly.',
        'Cheesecakes!',
        'Hey! This looks sketchy, not gonna lie.',
        'Have a good day...... or good night whatever.',
        'This has to be the matrix!',
        'Noob is you.',
        'Back to the future!',
        'We need a hashmap.',
        'Json, Jason, Jason, Jayson!'
    ]
    return random.choice(footers_list)

def generate_qr_code(id: str, text_to_embed: str):
    img = qrcode.make(text_to_embed)

    file_name = f'{id}.png'
    img.save(file_name)
    file = disnake.File(file_name, filename=file_name)

    return file_name, file

def generate_error_embed(title: str, description: str, footer_avatar):
    embed = (
        disnake.Embed(
            title=f'Whoops! {title}',
            description=description,
            color=accent_color[1]
        ).set_footer(
            text=generate_random_footer(),
            icon_url=footer_avatar
        )
    )
    return embed

async def has_voted(user_id: int):
    try:
        if await bot.topggpy.get_user_vote(user_id):
            return True
        else:
            return False
    except topgg.errors.Unauthorized:
        return None

async def is_frozen(message: disnake.Message):
    for frozen_guild in frozen_guilds:
        if frozen_guild[1] == message.guild.id and frozen_guild[2] == message.channel.id and frozen_guild[0] != message.author.id:
            await message.delete()
            return True

async def has_sweared(message: disnake.Message):
    if not message.author.bot:
        if profanity.contains_profanity(message.content):
            await message.delete()
            return True

async def is_jailed(message: disnake.Message):
    for jail_member in jail_members:
        if jail_member[1] == message.guild.id and jail_member[0] == message.author.id:
            await message.delete()
            return True

async def has_triggered_web_trap(message: disnake.Message):
    global msg_web_target
    global msg_web_records

    if msg_web_target:
        for target in msg_web_target:
            if target[0] == message.author.id:
                if len(msg_web_records) <= 5:
                    msg_web_records.append(message)
                else:
                    embed = (
                        disnake.Embed(
                            title='Web Trap Retracted', 
                            description='The web trap that you had enabled has been retracted successfully after it\'s operation. Below is the list of five messages that the web captured.',
                            color=accent_color[0]
                        )
                        .set_footer(
                            text=generate_random_footer(), 
                            icon_url=target[1].avatar
                        )
                    )
                    for message in msg_web_records:
                        embed.add_field(
                            name=f'\'{message.content}\'', 
                            value=f'Sent by {message.author.name} at {message.channel}'
                        )
                    await target[1].send(embed=embed)
                    msg_web_target = list()
                    msg_web_records = list()


# Checks.
def is_developer(ctx: commands.Context):
    if ctx.author.id == owner:
        return True


# Views (static).
class VoteCommandView(disnake.ui.View):
    def __init__(self, *, timeout: float=30):
        super().__init__(timeout=timeout)

        self.add_item(disnake.ui.Button(label='Vote Now', url='https://top.gg/bot/867998923250352189/vote'))
        self.add_item(disnake.ui.Button(label='Website', url='https://hitblast.github.io/Veron1CA'))

class HelpCommandView(disnake.ui.View):
    def __init__(self, *, timeout: float=30):
        super().__init__(timeout=timeout)

        self.add_item(disnake.ui.Button(label='Invite Me', url='https://discord.com/api/oauth2/authorize?client_id=867998923250352189&permissions=1039658487&scope=bot%20applications.commands'))
        self.add_item(disnake.ui.Button(label='Website', url='https://hitblast.github.io/Veron1CA'))
        self.add_item(disnake.ui.Button(label='Discord Server', url='https://discord.gg/6GNgcu7hjn'))


# Custom help command.
class HelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        ctx = self.context
        cogs_str = str()

        for cog in bot.cogs:
            if (cog == 'Developer') or (cog == 'ExceptionHandler'):
                pass
            else:
                cogs_str += f'> {cog}\n'
        
        embed = (
            disnake.Embed(
                title=f'It\'s {bot.user.name} onboard!', 
                color=accent_color[0]
            ).set_footer(
                text=f'Help requested by {ctx.author.name}',
                icon_url=ctx.author.avatar
            )
        ).add_field(
            name='Some quick, basic stuff...',
            value='I\'m an open source Discord music & moderation bot, and I can help you make customizing and modding your server easy as a feather! From blowing up scammers to freezing the entire crowded chat, there\'s a ton of stuff that I can do. Peace!'
        ).add_field(
            name='How to access me?',
            value=f'My command prefix is set to `{ctx.prefix}` and you can type `{ctx.prefix}help <category>` to get an entire list of usable commands depending on the category, or even type `{ctx.prefix}help <command>` to get information on a particular command.', 
            inline=False
        ).add_field(
            name='A bunch of categories',
            value=cogs_str,
            inline=False
        )

        await ctx.reply(embed=embed, view=HelpCommandView())

    async def send_cog_help(self, cog: commands.Cog):
        ctx = self.context
        commands_str = str()

        if cog.qualified_name == 'Developer':
            if not is_developer(ctx):
                return
        elif cog.qualified_name == 'ExceptionHandler':
            return

        for command in cog.get_commands():
            commands_str += f'> {command.name}\n'

        embed = (
            disnake.Embed(
                title=f'{cog.qualified_name} Commands',
                description=f'Below is an entire list of commands originating from the {cog.qualified_name} category. Type `{ctx.prefix}help <command>` to get help regarding a specific command.',
                color=accent_color[0]
            ).add_field(
                name='Usable commands:',
                value=commands_str
            ).set_footer(
                text=f'Cog help requested by {ctx.author.name}',
                icon_url=ctx.author.avatar
            )
        )
        await ctx.reply(embed=embed)

    async def send_command_help(self, command: commands.Command):
        ctx = self.context

        if command.cog_name == 'Developer':
            if not is_developer(ctx):
                return

        embed = (
            disnake.Embed(
                title=f'{command.cog_name} -> {command.name}', 
                color=accent_color[0]
            ).set_footer(
                text=f'Command help requested by {ctx.author.name}',
                icon_url=ctx.author.avatar
            )
        ).add_field(
            name='Description', 
            value=command.help,
            inline=False
        ).add_field(
            name='Usage', 
            value=f'`{ctx.prefix}{command.name} {command.signature}`', 
            inline=False
        )

        aliases = str()
        if command.aliases == []:
            aliases = "No aliases are available."
        else:
            aliases = str(command.aliases).replace(
                '[', '').replace(']', '').replace('\'', '')

        embed.add_field(
            name='Aliases', 
            value=aliases, 
            inline=False
        )
        await ctx.reply(embed=embed)

    async def send_error_message(self, error):
        ctx = self.context
        await ctx.reply(embed=generate_error_embed(title='This isn\'t a command.', description=error, footer_avatar=ctx.author.avatar))


# The main Bot class for root operations and events.
class Bot(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix, intents=disnake.Intents.all(), help_command=HelpCommand())

    async def on_connect(self):
        os.system('clear')
        print(f'{bot.user.name} | Read-only Terminal\n\nLog: Connected to Discord, warming up...')

    async def on_ready(self):
        print(f'Log: {bot.user.name} has been deployed in {len(bot.guilds)} server(s) with {bot.shard_count} shard(s) active.')
        await bot.change_presence(status=disnake.Status.dnd, activity=disnake.Activity(type=disnake.ActivityType.listening, name=f'{prefix}help and I\'m injected in {len(bot.guilds)} server(s)!'))

    async def on_message(self, message: disnake.Message):
        if message.author == bot.user:
            return

        try:
            if not db.search(Guild.id == message.guild.id):
                db.insert(
                    {
                        'id': message.guild.id, 
                        'prefix': None, 
                        'greet_members': False
                    }
                )
        except AttributeError:
            pass

        if not await has_sweared(message):
            if not await is_frozen(message):
                if not await is_jailed(message):
                    await bot.process_commands(message)
                    await has_triggered_web_trap(message)

    async def on_message_delete(self, message: disnake.Message):
        global snipeables
        snipeables.append(message)
        await asyncio.sleep(25)
        snipeables.remove(message)

    async def on_member_join(self, member: disnake.Member):
        guild = db.search(Guild.id == member.guild.id)
        if guild and guild[0]['greet_members']:
            await member.send(f'Welcome to {member.guild}, {member.mention}! Hope you enjoy your stay here.')


# Setting up the fundamentals.
uvloop.install()
bot = Bot()
bot.topggpy = topgg.DBLClient(bot, dbl_token)


# Custom exceptions.
class VoiceError(Exception):
    pass

class YTDLError(Exception):
    pass


# Global exception handler cog.
class ExceptionHandler(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        if hasattr(ctx.command, 'on_error'):
            return

        cog = ctx.cog
        if cog:
            if cog._get_overridden_method(cog.cog_command_error) is not None:
                return

        ignored = (commands.CommandNotFound, )
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        if isinstance(error, commands.DisabledCommand):
            await ctx.reply(embed=generate_error_embed(title='This command is disabled.', description=f'The command `{ctx.command}` has been disabled by the developer.', footer_avatar=ctx.author.avatar))

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                await ctx.reply(embed=generate_error_embed(title='This command can\'t be used in DMs.', description=f'The command `{ctx.command}` has been configured to only be executed in servers, not DM channels.', footer_avatar=ctx.author.avatar))
            except disnake.HTTPException:
                pass

        elif isinstance(error, commands.MissingRole):
            await ctx.reply(embed=generate_error_embed(title='You\'re missing a role!', description=error, footer_avatar=ctx.author.avatar))

        elif isinstance(error, commands.MissingAnyRole):
            await ctx.reply(embed=generate_error_embed(title='You\'re missing one of these roles.', description=error, footer_avatar=ctx.author.avatar))

        elif isinstance(error, commands.errors.UserNotFound):
            await ctx.reply(embed=generate_error_embed(title='The user wasn\'t found.', description=f'{error} Try mentioning or pinging them. You can also pass their ID as the argument.', footer_avatar=ctx.author.avatar))

        elif isinstance(error, commands.errors.MemberNotFound):
            await ctx.reply(embed=generate_error_embed(title='The member wasn\'t found.', description=f'{error} Try mentioning or pinging them. You can also pass their ID as the argument.', footer_avatar=ctx.author.avatar))

        elif isinstance(error, commands.errors.RoleNotFound):
            await ctx.reply(embed=generate_error_embed(title='The role wasn\'t found.', description=f'{error} Try mentioning or pinging it. You can also pass it\'s ID as the argument.', footer_avatar=ctx.author.avatar))

        elif isinstance(error, commands.errors.MissingRequiredArgument):
            await ctx.reply(embed=generate_error_embed(title='You\'re missing a required argument.', description=f'{error} Try typing `{ctx.prefix}help {ctx.command}` for more information on how to use this command.', footer_avatar=ctx.author.avatar))

        elif isinstance(error, commands.errors.CheckFailure):
            pass

        elif isinstance(error, disnake.errors.Forbidden):
            await ctx.reply(embed=generate_error_embed(title='The command couldn\'t be processed.', description='Either I\'m missing the required permissions or I just need to be at a higher position in the role hierarchy.', footer_avatar=ctx.author.avatar))

        elif isinstance(error, disnake.errors.NotFound):
            pass

        else:
            embed = (
                generate_error_embed(
                    title='An internal error occured.', 
                    description='If you think that it shouldn\'t happen, then try opening a ticket in our [support server]() and describe the issue. We\'ll try our best to demolish the bug for you (if it\'s there).', 
                    footer_avatar=ctx.author.avatar
                ).add_field(
                    name='Raised Error:',
                    value=f'```{error}```'
                )
            )
            await ctx.reply(embed=embed)
            print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    @commands.Cog.listener()
    async def on_slash_command_error(self, inter: ApplicationCommandInteraction, error):
        if isinstance(error, commands.NoPrivateMessage):
            await inter.response.send_message(embed=generate_error_embed(title='This command can\'t be used in DMs.', description=f'The command `{inter.data.name}` has been configured to only be executed in servers, not DM channels.', footer_avatar=inter.author.avatar))


# Chill category commands.
class Chill(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(
        name='avatar', 
        help='Shows a member\'s Discord avatar.',
    )
    @commands.guild_only()
    async def avatar(self, ctx: commands.Context, member: disnake.Member=None):
        if not member:
            member = ctx.message.author

        embed = (
            disnake.Embed(
                title='Here\'s what I found!', 
                color=accent_color[0]
            ).set_image(
                url=member.avatar
            ).set_footer(
                text=generate_random_footer(),
                icon_url=ctx.author.avatar
            )
        )
        await ctx.reply(embed=embed)

    @commands.slash_command(
        name='avatar',
        description='Shows a member\'s Discord avatar.',
        options=[
            Option("member", "Mention the server member.", OptionType.user)
        ]
    )
    @commands.guild_only()
    async def _avatar(self, inter: ApplicationCommandInteraction, member: disnake.Member=None):
        if not member:
            member = inter.author

        embed = (
            disnake.Embed(
                title='Here\'s what I found!', 
                color=accent_color[0]
            ).set_image(
                url=member.avatar
            ).set_footer(
                text=generate_random_footer(),
                icon_url=inter.author.avatar
            )
        )
        await inter.response.send_message(embed=embed)

    @commands.command(
        name='ping', 
        help='Shows my current response time.'
    )
    @commands.guild_only()
    async def ping(self, ctx: commands.Context):
        system_latency = round(self.bot.latency * 1000)

        start_time = time.time()
        message = await ctx.reply('Testing overall speed...')
        end_time = time.time()
        api_latency = round((end_time - start_time) * 1000)

        uptime = str(datetime.timedelta(seconds=int(
            round(time.time() - last_restarted_obj))))

        embed = (
            disnake.Embed(
                color=accent_color[0]
            ).add_field(
                name='System Latency', 
                value=f'{system_latency}ms [{self.bot.shard_count} shard(s)]', 
                inline=False
            ).add_field(
                name='API Latency',
                value=f'{api_latency}ms'
            ).add_field(
                name='Startup Time', 
                value=last_restarted_str, 
                inline=False
            ).add_field(
                name='Uptime', 
                value=uptime, 
                inline=False
            ).set_footer(
                text=generate_random_footer(),
                icon_url=ctx.author.avatar
            )
        )
        await message.edit(content=None, embed=embed)

    @commands.slash_command(
        name='ping',
        description='Shows my current response time.'
    )
    @commands.guild_only()
    async def _ping(self, inter: ApplicationCommandInteraction):
        ping = round(self.bot.latency * 1000)
        uptime = str(datetime.timedelta(seconds=int(round(time.time() - last_restarted_obj))))
        embed = (
            disnake.Embed(
                title='System Status', 
                color=accent_color[0]
            ).add_field(
                name='Latency', 
                value=f'{ping}ms [{self.bot.shard_count} shard(s)]', 
                inline=False
            ).add_field(
                name='Startup Time', 
                value=last_restarted_str, 
                inline=False
            ).add_field(
                name='Uptime', 
                value=uptime, 
                inline=False
            ).set_footer(
                text=generate_random_footer(),
                icon_url=inter.author.avatar
            )
        )
        await inter.response.send_message(embed=embed)

    @commands.command(
        name='vote', 
        help='Vote for me on Top.gg!'
    )
    @commands.guild_only()
    async def vote(self, ctx: commands.Context):
        vote = await has_voted(ctx.author.id)

        if vote is False:
            embed = (
                disnake.Embed(
                    title=':military_medal: Voting Section', 
                    description='Hey! Looks like you haven\'t voted for me today. If you\'re free, then be sure to check the links below to vote for me on Top.gg! It really helps my creator to get energetic and encourages him to launch more updates.',
                    color=accent_color[0]
                ).set_footer(
                    text=generate_random_footer(),
                    icon_url=ctx.author.avatar
                )
            )
            await ctx.reply(embed=embed, view=VoteCommandView())
            
        elif vote is True:
            await ctx.reply('You have already voted for me today, yay!')

        else:
            pass

    @commands.slash_command(
        name='vote',
        description='Vote for me on Top.gg!'
    )
    @commands.guild_only()
    async def _vote(self, inter: ApplicationCommandInteraction):
        vote = has_voted(inter.author.id)

        if vote is False:
            embed = (
                disnake.Embed(
                    title=':military_medal: Voting Section', 
                    description='Hey! Looks like you haven\'t voted for me today. If you\'re free, then be sure to check the links below to vote for me on Top.gg! It really helps my creator to get energetic and encourages him to launch more updates.',
                    color=accent_color[0]
                ).set_footer(
                    text=generate_random_footer(),
                    icon_url=inter.author.avatar
                )
            )
            await inter.response.send_message(embed=embed, view=VoteCommandView())
            
        elif vote is True:
            await inter.response.send_message('You have already voted for me today, yay!')

        else:
            await inter.response.send_message('Voting isn\'t a thing, by the way.')
            

# Casual category commands.
class Inspection(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(
        name='senddm', 
        help='Helps to send DMs to specific users.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def senddm(self, ctx: commands.Context, user: disnake.User, *, message: str):
        embed = (
            disnake.Embed(
                title=f'{ctx.author.name} has something up for you!', 
                color=accent_color[0]
            ).add_field(
                name='Message:', 
                value=message
            ).set_thumbnail(
                url=ctx.author.avatar
            ).set_footer(
                text='Delivered with <3 by Veron1CA!'
            )
        )
        await user.send(embed=embed)
        await ctx.send(f'{ctx.author.mention} your message has been sent!')
        await ctx.message.delete()

    @commands.command(
        name='userinfo', 
        help='Shows all important information on a user.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def userinfo(self, ctx: commands.Context, user: disnake.Member=None):
        if not user:
            user = ctx.author

        qr_file_name, qr_file = generate_qr_code(id=ctx.author.id, text_to_embed=f'https://discordapp.com/users/{ctx.author.id}/')

        embed = (
            disnake.Embed(
                color=accent_color[0]
            )
        ).add_field(
            name='Name', 
            value=user.name
        ).add_field(
            name='Status', 
            value=user.status
        ).add_field(
            name='Joining Date', 
            value=user.created_at.strftime("%b %d, %Y")
        ).add_field(
            name='Discriminator', 
            value=user.discriminator
        ).add_field(
            name='Race', 
            value='Bots, execute em!' if user.bot else 'Human'
        ).add_field(
            name='Roles', 
            value=len(user.roles)
        ).add_field(
            name='Identifier',
            value=user.id, 
            inline=False
        ).set_thumbnail(
            url=f'attachment://{qr_file_name}'
        )
        
        try:
            embed.set_footer(
                text=user.activities[0],
                icon_url=ctx.author.avatar
            )
        except:
            embed.set_footer(
                text=generate_random_footer(),
                icon_url=ctx.author.avatar
            )

        await ctx.reply(file=qr_file, embed=embed)
        
        if os.path.exists(qr_file_name):
            os.remove(qr_file_name)

    @commands.command(
        name='guildinfo', 
        help='Shows all important information on the current guild / server.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def guildinfo(self, ctx: commands.Context):
        guild = get_guild_dict(ctx.guild.id)
        embed = (
            disnake.Embed(
                title=ctx.guild.name,
                description=f'Showing all necessary information related to this guild. Scroll to find out more about {ctx.guild.name}!', 
                color=accent_color[0]
            )
        ).add_field(
            name='Creation Date',
            value=ctx.guild.created_at.strftime("%b %d, %Y")
        ).add_field(
            name='Region', 
            value=ctx.guild.region
        ).add_field(
            name='Server ID', 
            value=ctx.guild.id
        ).add_field(
            name='Members', 
            value=ctx.guild.member_count
        ).add_field(
            name='Roles', 
            value=len(ctx.guild.roles)
        ).add_field(
            name='Channels', 
            value=len(ctx.guild.channels)
        ).add_field(
            name='Command Prefix',
            value=prefix if not guild['prefix'] else guild['prefix']
        ).set_thumbnail(
            url=ctx.guild.icon
        ).set_footer(
            text=generate_random_footer(),
            icon_url=ctx.author.avatar
        )
        await ctx.reply(embed=embed)

    @commands.command(
        name='roleinfo', 
        help='Shows all important information related to a specific role.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def roleinfo(self, ctx: commands.Context, role: disnake.Role):
        embed = (
            disnake.Embed(
                title=f'Role Information: {str(role)}', 
                color=accent_color[0]
            )
        ).add_field(
            name='Creation Date:', 
            value=role.created_at.strftime("%b %d, %Y")
        ).add_field(
            name='Mentionable', 
            value=role.mentionable
        ).add_field(
            name='Managed By Integration', 
            value=role.is_integration()
        ).add_field(
            name='Managed By Bot', 
            value=role.is_bot_managed()
        ).add_field(
            name='Role Position', 
            value=role.position
        ).add_field(
            name='Role ID', 
            value=f'`{role.id}`'
        ).set_footer(
            text=generate_random_footer(),
            icon_url=ctx.author.avatar
        )
        await ctx.reply(embed=embed)

    @commands.command(
        name='audit', 
        help='Views the latest entries of the audit log in detail (limited to 100 entries).'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def audit(self, ctx: commands.Context, audit_limit: int):
        if int(audit_limit) > 100:
            await ctx.reply('Cannot send audit log entries more than 100 at a time!')

        else:
            embed = (
                disnake.Embed(
                    title='Audit Log', 
                    description=f'Showing the latest {audit_limit} entries that were made in the audit log of {ctx.guild.name}.', 
                    color=accent_color[0]
                ).set_footer(
                    text=generate_random_footer(), 
                    icon_url=ctx.author.avatar
                )
            )
            async for audit_entry in ctx.guild.audit_logs(limit=audit_limit):
                embed.add_field(
                    name=f'- {audit_entry.action}', 
                    value=f'User: {audit_entry.user} | Target: {audit_entry.target}', 
                    inline=False
                )
            await ctx.reply(embed=embed)


# Moderation category commands.
class Moderation(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(
        name='purge', 
        help='Clears messages within the given index.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def purge(self, ctx: commands.Context, amount: int=1):
        if amount > 200:
            await ctx.reply('Purges are limited to 200 messages per use!')
        else:
            amount += 1
            await ctx.channel.purge(limit=amount)

    @commands.command(
        name='ripplepurge', 
        help='Clears messages that are sent by a specific user within the given index.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def ripplepurge(self, ctx: commands.Context, member: disnake.Member, amount: int=2):
        if amount > 100:
            await ctx.reply('Ripple purges are limited to 100 messages per use!')
        else:
            await ctx.message.add_reaction('✅')
            messages = await ctx.history(limit=amount).flatten()

            for message in messages:
                if message.author == member:
                    await message.delete()

    @commands.command(
        name='msgweb', 
        help='Enables a web trap to capture six messages sent by a specific user.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def msgweb(self, ctx: commands.Context, member: disnake.Member):
        global msg_web_target

        if not msg_web_target:
            msg_web_target.append([member.id, ctx.author])
            await ctx.author.send(f'A message web trap on {member.name} has been triggered. The captured messages will be delivered to you shortly after the web has completed it\'s task.')
            await ctx.message.delete()

        else:
            await ctx.author.send('Something fishy is already going on. Try again later!')
            await ctx.message.delete()

    @commands.command(
        name='snipemsg',
        help='Snipes a recent message from the channel.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def snipemsg(self, ctx: commands.Context):
        if snipeables:
            for snipeable in snipeables:
                if snipeable.guild == ctx.guild:
                    webhook = await ctx.message.channel.create_webhook(name=snipeable.author.name)
                    await webhook.send(snipeable.content, username=snipeable.author.name, avatar_url=snipeable.author.avatar)
                    await webhook.delete()

        else:
            await ctx.reply('No messages were found in my list.')

    @commands.command(
        name='jail', 
        help='Temporarily prevents a member from chatting in server.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def jail(self, ctx: commands.Context, member: disnake.Member, *, reason: str='No reason provided.'):
        do_jail = False

        if member != self.bot.user:
            if member != ctx.author:
                if member.guild_permissions.administrator:
                    if ctx.author.guild_permissions.administrator:
                        do_jail = True
                    else:
                        await ctx.reply('You can\'t jail an admin!')
                else:
                    do_jail = True
            else:
                await ctx.reply('You can\'t jail yourself!')
        else:
            await ctx.reply('Why are you even trying to jail me?')

        if do_jail:
            jail_members.append([member.id, ctx.guild.id, reason, ctx.author.id])
            await ctx.send(f'You\'ve been captured! {member.mention} | Reason: {reason}')
            await ctx.message.delete()

    @commands.command(
        name='jailed', 
        help='Views jailed members.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def jailed(self, ctx: commands.Context):
        jail_has_member = False
        embed = (
            disnake.Embed(
                title='Now viewing the prison!', 
                color=accent_color[0]
            ).set_footer(
                icon_url=ctx.author.avatar, 
                text=generate_random_footer()
            )
        )
        for jail_member in jail_members:
            if jail_member[1] == ctx.guild.id:
                embed.add_field(
                    name=self.bot.get_user(jail_member[0]).name, 
                    value=('Jailed by ' + self.bot.get_user(jail_member[3]).mention + ' | Reason: `' + jail_member[2] + '`'), 
                    inline=False
                )
                jail_has_member = True

        if jail_has_member is False:
            await ctx.reply('No members are inside the jail.')

        else:
            await ctx.reply(embed=embed)

    @commands.command(
        name='unjail', 
        help='Removes a member from jail.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def unjail(self, ctx: commands.Context, member: disnake.Member):
        for jail_member in jail_members:
            if jail_member[1] == ctx.guild.id and jail_member[0] == member.id:
                if member != ctx.author:
                    jail_members.remove(jail_member)
                    await ctx.message.add_reaction('✅')

                else:
                    await ctx.reply('You can\'t free yourself!')

    @commands.command(
        name='block', 
        help='Blocks a user from chatting in a specific channel.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def block(self, ctx: commands.Context, member: disnake.Member, *, reason: str='No reason provided.'):
        if member != self.bot.user:
            if member != ctx.author:
                await ctx.channel.set_permissions(member, send_messages=False)
                await ctx.send(f'You\'re now blocked from chatting, {member.mention} | Reason: {reason}')
                await ctx.message.delete()

            else:
                await ctx.reply(f'You can\'t block yourself!')
        else:
            await ctx.reply(f'Why are you even trying to block me?')

    @commands.command(
        name='unblock', 
        help='Unblocks a user.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def unblock(self, ctx: commands.Context, member: disnake.Member):
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.message.add_reaction('✅')

    @commands.command(
        name='kick', 
        help='Kicks a member from server.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def kick(self, ctx: commands.Context, member: disnake.User, *, reason: str='No reason provided.'):
        await ctx.guild.kick(member, reason=reason)
        await ctx.send(f'**{member.name}** has been kicked! Reason: {reason}')
        await ctx.message.delete()

    @commands.command(
        name='ban', 
        help='Bans a member from server.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def ban(self, ctx: commands.Context, member: disnake.User, *, reason: str='No reason provided.'):
        await ctx.guild.ban(member, reason=reason)
        await ctx.send(f'**{member.name}** has been banned! Reason: {reason}')
        await ctx.message.delete()

    @commands.command(
        name='bans', 
        help='Shows a list of banned users in the server.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def bans(self, ctx: commands.Context):
        bans = await ctx.guild.bans()
        embed = (
            disnake.Embed(
                title='Now viewing banned members!', 
                color=accent_color[0]
            ).set_footer(
                icon_url=ctx.author.avatar, 
                text=generate_random_footer()
            )
        )
        if bans:
            for ban in bans:
                embed.add_field(
                    name=ban.user, 
                    value=f'ID: `{ban.user.id}` | Reason: `{ban.reason}`', 
                    inline=False
                )
            await ctx.reply(embed=embed)

        else:
            await ctx.reply('No members are banned from this server.')

    @commands.command(
        name='unban', 
        help='Unbans a member in server.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def unban(self, ctx: commands.Context, member: disnake.User):
        await ctx.guild.unban(member)
        await ctx.reply(f'Member **{member.name}** has been unbanned!')

    @commands.command(
        name='freeze', 
        help='Calms down chat.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles[1])
    async def freeze(self, ctx: commands.Context):
        frozen_guilds.append([ctx.author.id, ctx.guild.id, ctx.message.channel.id])
        await ctx.send(f'**Chat was frozen by {ctx.author.mention}!**')
        await ctx.message.delete()

    @commands.command(
        name='thaw', 
        help='Removes frozen state from chat.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles[1])
    async def thaw(self, ctx: commands.Context):
        for frozen_guild in frozen_guilds:
            if frozen_guild[1] == ctx.guild.id:
                frozen_guilds.remove(frozen_guild)
                await ctx.message.add_reaction('✅')


# Customization category commands.
class Customization(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(
        name='makeinv', 
        help='Creates an invite code or link.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def makeinv(self, ctx: commands.Context, max_age=60, max_uses=1, *, reason: str='No reason provided.'):
        if not reason:
            reason = f'Inviter: {ctx.author.name}'

        invite = await ctx.channel.create_invite(max_age=max_age, max_uses=max_uses, reason=reason)
        embed = (
            disnake.Embed(
                color=accent_color[0]
            ).add_field(
                name='Link', 
                value=invite
            ).add_field(
                name='ID', 
                value=f'`{invite.id}`'
            ).add_field(
                name='Channel', 
                value=invite.channel
            ).set_author(
                name='An invite was created!', 
                icon_url=ctx.author.avatar
            )
        )

        value = str()
        if invite.max_age == 0:
            value = 'Infinity'
        else:
            value = f'{invite.max_age} Seconds'

        embed.add_field(
            name='Lifetime', 
            value=value
        ).add_field(
            name='Max Uses', 
            value=invite.max_uses
        )
        await ctx.reply(embed=embed)

    @commands.command(
        name='invites', 
        help='Shows all active server invite codes.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles[0], lock_roles[1])
    async def invites(self, ctx: commands.Context):
        invites = await ctx.guild.invites()
        embed = (
            disnake.Embed(
                title='Now viewing invite codes!', 
                color=accent_color[0]
            ).set_footer(
                icon_url=ctx.author.avatar, 
                text=generate_random_footer()
            )
        )

        if not invites:
            await ctx.reply('No invite codes have been generated.')

        else:
            invcount = 0
            for invite in invites:
                invcount += 1
                embed.add_field(
                    name=invite, 
                    value=f'Uses: {invite.uses} | Inviter: {invite.inviter.name} | ID: `{invite.id}`', 
                    inline=False
                )
            await ctx.reply(embed=embed)

    @commands.command(
        name='removeinv', 
        help='Removes a previously generated invite code or link.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles[1])
    async def removeinv(self, ctx: commands.Context, invite_id: str):
        invites = await ctx.guild.invites()
        for invite in invites:
            if invite.id == invite_id:
                await invite.delete()
                await ctx.reply('Invite has been deleted.')
                
    @commands.command(
        name='makerole', 
        help='Creates a role.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles[1])
    async def makerole(self, ctx: commands.Context, *, role):
        await ctx.guild.create_role(name=role)
        await ctx.message.add_reaction('✅')

    @commands.command(
        name='removerole', 
        help='Removes an existing role.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles[1])
    async def removerole(self, ctx: commands.Context, *, role: disnake.Role):
        if role is None:
            await ctx.reply('That\'s not a role, I guess?')

        else:
            await role.delete()
            await ctx.message.add_reaction('✅')

    @commands.command(
        name='assignrole', 
        help='Assigns an existing role to a server member.', pass_context=True
    )
    @commands.guild_only()
    @commands.has_role(lock_roles[1])
    async def assignrole(self, ctx: commands.Context, role: disnake.Role, member: disnake.Member):
        await member.add_roles(role)
        await ctx.reply(f'Role {role.mention} has been given to {member.mention}, peace! :partying_face:')

    @commands.command(
        name='nick',
        value='Changes the nickname of a member.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles[1])
    async def nick(self, ctx: commands.Context, member: disnake.Member, nick: str):
        await member.edit(nick=nick)
        await ctx.message.add_reaction('✅')

    @commands.command(
        name='makech', 
        help='Creates a server channel.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles[1])
    async def makech(self, ctx: commands.Context, *, channel_name: str):
        guild = ctx.guild
        existing_channel = disnake.utils.get(guild.channels, name=channel_name)
        if not existing_channel:
            await guild.create_text_channel(channel_name)
            await ctx.message.add_reaction('✅')

    @commands.command(
        name='removech', 
        help='Removes an existing server channel.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles[1])
    async def removech(self, ctx: commands.Context, channel_name: disnake.TextChannel):
        await channel_name.delete()
        await ctx.message.add_reaction('✅')


# Tweaks category commands.
class Tweaks(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot 

    @commands.command(
        name='prefix',
        help='Shows / changes the server\'s default command prefix.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles[1])
    async def prefix(self, ctx: commands.Context, prefix: str=None):
        db.update({'prefix': prefix}, Guild.id == ctx.guild.id)
        await ctx.reply(f'Changed server prefix to `{prefix}`!')

    @commands.command(
        name='greetings',
        help='Toggles the greeting message which is sent to an incoming Discord user upon joining.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles[1])
    async def toggle_greeting(self, ctx: commands.Context):
        greet_members = get_guild_dict(ctx.guild.id)['greet_members']
        db.update({'greet_members': not greet_members}, Guild.id == ctx.guild.id)
        greet_members = get_guild_dict(ctx.guild.id)['greet_members']
        await ctx.reply(f'Greetings have been toggled to `{greet_members}`!')


# Music category commands.
youtube_dl.utils.bug_reports_message = lambda: ''

class YTDLSource(disnake.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)
    ytdl.cache.remove()

    def __init__(self, ctx: commands.Context, source: disnake.FFmpegPCMAudio, *, data: dict, volume: float=0.5):
        super().__init__(source, volume)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data

        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.tags = data.get('tags')
        self.url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.stream_url = data.get('url')

    def __str__(self):
        return "**{0.title}** by **{0.uploader}**".format(self)

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(
            cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)

        if data is None:
            raise YTDLError(
                'Couldn\'t find anything that matches **{}**'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError('Couldn\'t find anything that matches **{}**'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(
            cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)

        if processed_info is None:
            raise YTDLError('Couldn\'t fetch **{}**'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError('Couldn\'t retrieve any matches for **{}**'.format(webpage_url))

        return cls(ctx, disnake.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{} days'.format(days))
        if hours > 0:
            duration.append('{} hours'.format(hours))
        if minutes > 0:
            duration.append('{} minutes'.format(minutes))
        if seconds > 0:
            duration.append('{} seconds'.format(seconds))

        return ', '.join(duration)


# Views (static / dynamic, for music commands).
class NowCommandView(disnake.ui.View):
    def __init__(self, *, url=str, views=str, likes=str, timeout: float=30):
        super().__init__(timeout=timeout)

        self.add_item(disnake.ui.Button(label='Redirect', url=url))
        self.add_item(disnake.ui.Button(label=f'{int(views):,} Views', style=disnake.ButtonStyle.grey))
        self.add_item(disnake.ui.Button(label=f'{int(likes):,} Likes', style=disnake.ButtonStyle.grey))


class Song:
    __slots__ = ('source', 'requester')

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester

    def create_embed(self):
        duration = 'Live' if not self.source.duration else self.source.duration

        embed = (
            disnake.Embed(
                title=f'{self.source.title}',
                color=accent_color[0]
            ).add_field(
                name='Duration', 
                value=duration
            ).add_field(
                name='Requested by', 
                value=self.requester.mention
            ).set_image(
                url=self.source.thumbnail
            )
        )
        view = NowCommandView(url=self.source.url, views=self.source.views, likes=self.source.likes)
        return embed, view


class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]


class VoiceState:
    def __init__(self, bot: commands.AutoShardedBot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx

        self.current = None
        self.voice = None
        self.exists = True
        self.next = asyncio.Event()
        self.songs = SongQueue()

        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()
            self.now = None

            if self.loop == False:
                try:
                    async with timeout(180):
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    self.exists = False
                    return
                
                self.current.source.volume = self._volume
                self.voice.play(self.current.source, after=self.play_next_song)

            elif self.loop:
                self.now = disnake.FFmpegPCMAudio(self.current.source.stream_url, **YTDLSource.FFMPEG_OPTIONS)
                self.voice.play(self.now, after=self.play_next_song)
            
            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        self.skip_votes.clear()

        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()

        if self.voice:
            await self.voice.disconnect()
            self.voice = None


# Music category commands.
class Music(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.voice_states = dict()

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state or not state.exists:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    @commands.command(
        name='join', 
        help='Joins a specific voice channel.', 
        invoke_without_subcommand=True
    )
    @commands.guild_only()
    async def _join(self, ctx: commands.Context):
        destination = ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        await ctx.message.add_reaction('✅')
        ctx.voice_state.voice = await destination.connect()

    @commands.command(
        name='summon', 
        help='Summons Veron1CA to a particular voice channel.'
    )
    @commands.guild_only()
    async def _summon(self, ctx: commands.Context, *, channel: disnake.VoiceChannel=None):
        if not channel and not ctx.author.voice:
            raise VoiceError('You are neither connected to a voice channel nor specified a channel to join.')

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()
        await ctx.message.add_reaction('✅')

    @commands.command(
        name='leave', 
        help='Clears the queue and leaves the voice channel.'
    )
    @commands.guild_only()
    async def _leave(self, ctx: commands.Context):
        if not ctx.voice_state.voice:
            return await ctx.reply('I am not connected to any voice channel.')
        elif not ctx.author.voice:
            return await ctx.reply('You are not in the same voice channel as mine.')
 
        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]
        await ctx.message.add_reaction('✅')

    @commands.command(
        name='volume', 
        help='Sets the volume of the player.'
    )
    @commands.guild_only()
    async def _volume(self, ctx: commands.Context, *, volume: int):
        vote = await has_voted(ctx.author.id)

        if (vote is None) or (vote is True):
            if not ctx.voice_state.is_playing:
                return await ctx.reply('There\'s nothing being played at the moment.')

            if 0 >= volume >= 100:
                return await ctx.reply('Volume must be between 0 and 100 to execute the command.')

            ctx.voice_state.current.source.volume = volume / 100
            await ctx.reply(f'Volume of the player is now set to **{volume}%**')

        else:
            embed = (
                disnake.Embed(
                    title='Whoops! This command is locked.',
                    description=f'By voting for me on Top.gg, you\'ll unlock `{ctx.command}` and all other locked commands for 12 hours.',
                    color=accent_color[1]
                ).set_footer(
                    text='It\'s free, it only takes a minute to do and it also supports my creator a lot!',
                    icon_url=ctx.author.avatar
                )
            )
            await ctx.reply(embed=embed, view=VoteCommandView())

    @commands.command(
        name='now', 
        help='Displays the currently playing song.'
    )
    @commands.guild_only()
    async def _now(self, ctx: commands.Context):
        try:
            embed, view = ctx.voice_state.current.create_embed()
            await ctx.reply(embed=embed, view=view)
        except AttributeError:
            await ctx.reply('There\'s nothing being played at the moment.')

    @commands.command(
        name='pause', 
        help='Pauses the currently playing song.'
    )
    @commands.guild_only()
    async def _pause(self, ctx: commands.Context):
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('✅')

    @commands.command(
        name='resume', 
        help='Resumes a currently paused song.'
    )
    @commands.guild_only()
    async def _resume(self, ctx: commands.Context):
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('✅')

    @commands.command(
        name='stop', 
        help='Stops playing song and clears the queue.'
    )
    @commands.guild_only()
    async def _stop(self, ctx: commands.Context):
        ctx.voice_state.songs.clear()

        if ctx.voice_state.is_playing:
            if ctx.voice_state.loop:
                ctx.voice_state.loop = not ctx.voice_state.loop

            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('✅')

    @commands.command(
        name='skip', 
        help='Vote to skip a song. The requester can automatically skip.'
    )
    @commands.guild_only()
    async def _skip(self, ctx: commands.Context):
        if not ctx.voice_state.is_playing:
            return await ctx.reply('Not playing any music right now, so no skipping for you.')

        voter = ctx.author
        if voter == ctx.voice_state.current.requester:
            await ctx.message.add_reaction('✅')
            ctx.voice_state.skip()

        elif voter.id not in ctx.voice_state.skip_votes:
            ctx.voice_state.skip_votes.add(voter.id)
            total_votes = len(ctx.voice_state.skip_votes)

            if total_votes >= 3:
                await ctx.message.add_reaction('✅')
                ctx.voice_state.skip()
            else:
                await ctx.reply('Skip vote added, currently at **{}/3** votes.'.format(total_votes))

        else:
            await ctx.reply('You have already voted to skip this song.')

    @commands.command(
        name='queue', 
        help='Shows the player\'s queue.'
    )
    @commands.guild_only()
    async def _queue(self, ctx: commands.Context, *, page: int=1):
        if len(ctx.voice_state.songs) == 0:
            return await ctx.reply('Empty queue.')

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

        start = (page - 1) * items_per_page
        end = start + items_per_page

        queue = ''
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(
                i + 1, song)

        embed = (
            disnake.Embed(
                description='**{} tracks:**\n\n{}'.format(len(ctx.voice_state.songs), queue)
            ).set_footer(
                text='Viewing page {}/{}'.format(page, pages)
            )
        )
        await ctx.reply(embed=embed)

    @commands.command(
        name='shuffle', 
        help='Shuffles the queue.'
    )
    @commands.guild_only()
    async def _shuffle(self, ctx: commands.Context):
        if len(ctx.voice_state.songs) == 0:
            return await ctx.reply('The queue is empty, play some songs, maybe?')

        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(
        name='remove',
        help='Removes a song from the queue at a given index.'
    )
    @commands.guild_only()
    async def _remove(self, ctx: commands.Context, index: int):
        if len(ctx.voice_state.songs) == 0:
            return await ctx.reply('The queue is empty, so nothing to be removed.')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(
        name='loop', 
        help='Enables no-timeout looping for music playback.'
    )
    @commands.guild_only()
    async def _loop(self, ctx: commands.Context):
        vote = await has_voted(ctx.author.id)

        if (vote is None) or (vote is True):
            if not ctx.voice_state.is_playing:
                return await ctx.reply('There\'s nothing being played at the moment.')

            ctx.voice_state.loop = not ctx.voice_state.loop

            embed = (
                disnake.Embed(
                    title='Looping right now...' if ctx.voice_state.loop else 'Looping stopped...',
                    color=accent_color[0]
                ).set_footer(
                    text=generate_random_footer(),
                    icon_url=ctx.author.avatar
                )
            )

            await ctx.reply(embed=embed)
        
        else:
            embed = (
                disnake.Embed(
                    title='Whoops! This command is locked.',
                    description=f'By voting for me on Top.gg, you\'ll unlock `{ctx.command}` and all other locked commands for 12 hours.',
                    color=accent_color[1]
                ).set_footer(
                    text='It\'s free, it only takes a minute to do and it also supports my creator a lot!',
                    icon_url=ctx.author.avatar
                )
            )
            await ctx.reply(embed=embed, view=VoteCommandView())

    @commands.command(
        name='play', 
        help='Plays music for you.'
    )
    @commands.guild_only()
    async def _play(self, ctx: commands.Context, *, search: str):
        if not ctx.voice_state.voice:
            await ctx.invoke(self._join)

        async with ctx.typing():
            try:
                source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                await ctx.reply('Whoops! An error occurred while processing this request: {}'.format(str(e)))
            else:
                song = Song(source)

                await ctx.voice_state.songs.put(song)
                await asyncio.sleep(1)
                await ctx.invoke(self._now)

    @_join.before_invoke
    @_play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to any voice channel.')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('I\'m already in a voice channel.')


# Developer commands/tools.
class Developer(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(
        name='restart', 
        help='Fetches the latest code from the Git repository of the project and restarts.'
    )
    @commands.check(is_developer)
    async def restart(self, ctx: commands.Context):
        try:
            _ = git.Repo(os.getcwd()).git_dir
            embed = (
                disnake.Embed(
                    title=f'Fetching latest code for me...', 
                    description='I will automatically restart when the possible updates are done setting up! Please be patient.',
                    color=accent_color[0]
                ).set_footer(
                    text=generate_random_footer(), 
                    icon_url=ctx.author.avatar
                )
            )
            await ctx.reply(embed=embed)
            os.system('git pull origin master')

        except git.exc.InvalidGitRepositoryError:
            await ctx.reply('I am not connected with a Git repository, so I can\'t retrieve the latest code. Restarting anyway...')

        finally:
            os.execv(sys.executable, ['python'] + sys.argv)

    @commands.command(
        name='close', 
        help='Closes the connection to Discord.'
    )
    @commands.check(is_developer)
    async def logout(self, ctx: commands.Context):
        await ctx.message.add_reaction('✅')
        await self.bot.close()    


# Optional support layer for ensuring better uptime on cloud hosting services (e.g. Replit).
keep_alive_toggle = True

# Change the value of `keep_alive_toggle` to True if the module needs to be used.
if keep_alive_toggle:
    app = Flask('')
    @app.route('/')

    def home():
        return f"<h2>{bot.user.name} is now live!</h2>"

    def run():
        app.run(host='0.0.0.0', port=8080)
        
    t = Thread(target=run)
    t.start()


# Add available cogs.
bot.add_cog(ExceptionHandler(bot))
bot.add_cog(Chill(bot))
bot.add_cog(Inspection(bot))
bot.add_cog(Moderation(bot))
bot.add_cog(Customization(bot))
bot.add_cog(Tweaks(bot))
bot.add_cog(Music(bot))
bot.add_cog(Developer(bot))


# Run the bot.
bot.run(token)