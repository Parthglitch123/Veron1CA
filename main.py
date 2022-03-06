'''
MIT License

Copyright (c) 2021-present HitBlast

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''



# Import built-in libraries.
import os
import sys
import json
import math
import time
import uvloop
import random
import asyncio
import datetime
import functools
import itertools
import traceback
from threading import Thread
from typing import Any, List, Dict

# Import third-party libraries.
import topgg
import qrcode
import youtube_dl
from flask import Flask, jsonify
from tinydb import TinyDB, Query
from async_timeout import timeout
from better_profanity import profanity
from decouple import config, UndefinedValueError

# Import the API wrapper for Discord and its components.
import disnake
from disnake import Option, OptionType
from disnake.ext import commands, tasks

# Import the API wrapper for Spotify.
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


# Environment variables.
try:
    tokens: Dict[str, str] = {
        'discord': config('DISCORD_TOKEN', cast=str),
        'spotify': config('SPOTIFY_CLIENT_SECRET', cast=str),
        'topggpy': config('DBL_TOKEN', default=None, cast=str)
    }
    owner_ids: Dict[str, int | str] = {
        'discord': config('DISCORD_OWNER_ID', cast=int),
        'spotify': config('SPOTIFY_CLIENT_ID', cast=str)
    }
    prefix = config('COMMAND_PREFIX', default='vrn.', cast=str)

except UndefinedValueError:
    print('One or more secrets have been left undefined. Consider going through the README.md file for proper instructions on setting Veron1CA up.')
    time.sleep(5)
    exit()


# Core dictionaries and variables.
datetime_format_str = "%d/%m/%Y | %H:%M:%S"
reaction_emoji = '☑️'

accent_color: Dict[str, int] = {
    'primary': 0, 
    'error': 14573921
}
lock_roles: Dict[str, str] = {
    'moderator': 'BotMod', 
    'admin': 'BotAdmin'
}


# Store startup data.
startup_data = {
    'str': str(datetime.datetime.now().strftime(datetime_format_str)),
    'obj': time.time()
}


# Implementation of the profanity filter.
profanity.load_censor_words_from_file('filtered.txt')

# Implementation of the guild database.
db = TinyDB('guild-db.json')
Guild = Query()

# Implementation of Spotipy.
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=owner_ids['spotify'], 
        client_secret=tokens['spotify']
    )
)


# Global variables.
global jail_members
jail_members: List[int | str] = []
global frozen_guilds
frozen_guilds: List[int] = []
global snipeables
snipeables: List[disnake.Message] = []


# Get prefix by guild ID.
def get_prefix(bot: commands.AutoShardedBot, message: disnake.Message):
    guild_prefix = prefix

    try:
        for guild in db.all():
            if guild['id'] == message.guild.id and guild['prefix']:
                guild_prefix = guild['prefix']
    except AttributeError:
        pass

    return commands.when_mentioned_or(guild_prefix)(bot, message)


# Functions / coroutines (for using across the source).
def get_guild_dict(id: int) -> dict:
    guild = db.search(Guild.id == id)
    return guild[0] if guild else None

def generate_random_footer() -> str:
    footers_list = [
        'Hey there pal :D',
        'Hey! Want some pants?',
        'When pigs fly.',
        'When you\'re not looking...',
        'Cheesecakes!',
        'Hey! This looks sketchy, not gonna lie.',
        'Have a good day... or good night, whatever.',
        'This has to be the matrix!',
        'Noob is you.',
        'Back to the future!',
        'We need a hashmap.',
        'I\'m not a robot.',
        'I\'m not a fan of you.',
        'Steven, use failure!',
        'Json, Jason, Jason, Jayson!'
    ]
    return random.choice(footers_list)

def generate_qr_code(id: int, text_to_embed: str):
    img = qrcode.make(text_to_embed)

    file_name = f'{id}.png'
    img.save(file_name)
    file = disnake.File(file_name, filename=file_name)

    return file_name, file

def generate_error_embed(title: str, description: str, footer_avatar) -> disnake.Embed:
    return (
        disnake.Embed(
            title=f'Whoops! {title}',
            description=description,
            color=accent_color['error']
        ).set_footer(
            text=generate_random_footer(),
            icon_url=footer_avatar
        )
    )

async def check_if_voted(id: int) -> bool:
    try:
        return bool(await bot.topggpy.get_user_vote(id))
    except topgg.errors.Unauthorized:
        return None

async def wait_for_message(member: disnake.Member, check_if_member: bool) -> disnake.Message:
    def is_author(message: disnake.Message):
        return (message.author == member) if check_if_member else (message.author != member)

    message = await bot.wait_for('message', check=is_author, timeout=30)
    return message

async def check_if_frozen(message: disnake.Message) -> bool:
    for frozen_guild in frozen_guilds:
        if frozen_guild[1] == message.guild.id and frozen_guild[2] == message.channel.id and frozen_guild[0] != message.author.id:
            await message.delete()
            return True

async def check_if_swore(message: disnake.Message) -> bool:
    guild = get_guild_dict(message.guild.id)
    if (
        not message.author.bot
        and message.channel != disnake.DMChannel
        and not message.channel.is_nsfw()
        and profanity.contains_profanity(message.content)
        and guild['filter_profanity']
    ):
        await message.delete()
        return True

async def check_if_jailed(message: disnake.Message) -> bool:
    for jail_member in jail_members:
        if jail_member[1] == message.guild.id and jail_member[0] == message.author.id:
            await message.delete()
            return True


# Command-specific checks.
def is_developer(ctx: commands.Context) -> bool:
    return ctx.author.id == owner_ids['discord']


# Dropdowns (dynamic).
class HelpCommandDropdown(disnake.ui.Select):
    def __init__(self):
        options = [
            disnake.SelectOption(
                label="Chill", description="Casual commands for everyone."
            ),
            disnake.SelectOption(
                label="Inspection", description="Commands to spectate stuff."
            ),
            disnake.SelectOption(
                label="GeneralMod", description="Commands to use in moderation."
            ),
            disnake.SelectOption(
                label="VoiceMod", description="Moderation, but for voice."
            ),
            disnake.SelectOption(
                label="Customization", description="Commands to customize your server."
            ),
            disnake.SelectOption(
                label="Tweaks", description="Tweak your experience with this category of commands."
            ),
            disnake.SelectOption(
                label="Music", description="The vibe is real!"
            )
        ]

        super().__init__(
            placeholder="Choose your category of commands.",
            options=options
        )

    async def callback(self, inter: disnake.MessageInteraction):
        cog = bot.get_cog(self.values[0])
        commands_str = ''

        for command in cog.get_commands():
            commands_str += f'> {command.name}\n'

        embed = (
            disnake.Embed(
                title=f'{cog.qualified_name} Commands',
                description=f'Below is an entire list of commands originating from the {cog.qualified_name} category. Type the `help` command followed by your command (choose from below) to learn more about it.',
                color=accent_color['primary']
            ).add_field(
                name='Usable commands:',
                value=commands_str
            ).set_footer(
                text=f'Cog help requested by {inter.author.name}',
                icon_url=inter.author.avatar
            )
        )
        await inter.response.edit_message(embed=embed)


# Views (static).
class VoteCommandView(disnake.ui.View):
    def __init__(self, timeout: float=10):
        super().__init__(timeout=timeout)

        self.add_item(disnake.ui.Button(label='Vote Now', url='https://top.gg/bot/867998923250352189/vote'))
        self.add_item(disnake.ui.Button(label='Website', url='https://hitblast.github.io/Veron1CA'))

class HelpCommandView(disnake.ui.View):
    def __init__(self, timeout: float=10):
        super().__init__(timeout=timeout)

        self.add_item(HelpCommandDropdown())
        self.add_item(disnake.ui.Button(label='Invite Me', url='https://discord.com/api/oauth2/authorize?client_id=867998923250352189&permissions=1506458988023&scope=bot%20applications.commands'))
        self.add_item(disnake.ui.Button(label='Website', url='https://hitblast.github.io/Veron1CA'))
        self.add_item(disnake.ui.Button(label='Support Server', url='https://discord.gg/6GNgcu7hjn'))  


# Custom help command.
class HelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping: Any):
        ctx = self.context
        cogs_str = ''

        for cog in bot.cogs:
            if cog not in ['Developer', 'ExceptionHandler']:
                cogs_str += f'> {cog}\n'

        embed = (
            disnake.Embed(
                title=f'It\'s {bot.user.name} onboard!', 
                color=accent_color['primary']
            ).set_footer(
                text=f'Help requested by {ctx.author.name}',
                icon_url=ctx.author.avatar
            )
        ).add_field(
            name='Some quick, basic stuff...',
            value='I\'m an open source Discord music & moderation bot, and I can help you make customizing and modding your server easy as a feather! From blowing up scammers to freezing the entire crowded chat, there\'s a ton of stuff that I can do.'
        ).add_field(
            name='How to access me?',
            value=f'My command prefix is set to `{ctx.prefix}` and you can select the category from the dropdown below to get a list of usable commands, or even type `{ctx.prefix}help <command>` to get information on a particular command.', 
            inline=False
        )

        await ctx.reply(embed=embed, view=HelpCommandView())

    async def send_command_help(self, command: commands.Command):
        ctx = self.context

        if command.cog_name == 'Developer' and not is_developer(ctx):
            return

        embed = (
            disnake.Embed(
                title=f'{command.cog_name} -> {command.name}', 
                color=accent_color['primary']
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

        if not command.aliases:
            aliases = "No aliases are available."
        else:
            aliases = ', '.join(command.aliases)

        embed.add_field(
            name='Aliases', 
            value=aliases, 
            inline=False
        )
        await ctx.reply(embed=embed)

    async def send_error_message(self, error):
        await self.context.reply(embed=generate_error_embed(title='This isn\'t a command!', description=error, footer_avatar=self.context.author.avatar))


# The main Bot class for root operations and events.
class Bot(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(
            command_prefix=get_prefix, 
            intents=disnake.Intents.all(), 
            help_command=HelpCommand(), 
            strip_after_prefix=True, 
            case_insensitive=True
        )
        
        self.task_update_presence.start()

    async def on_connect(self):
        os.system('clear')
        print(f'{self.user} | Connected to Discord\n')

    async def on_ready(self):
        print(f'I\'ve been deployed in {len(self.guilds)} server(s) with {self.shard_count} shard(s) active.')

    @tasks.loop(seconds=200)
    async def task_update_presence(self):
        await self.change_presence(
            status=disnake.Status.dnd, 
            activity=disnake.Activity(
                type=disnake.ActivityType.listening, 
                name=f'{prefix}help | Injected in {len(self.guilds)} server(s)!'
            )
        )

    @task_update_presence.before_loop
    async def task_before_updating_presence(self):
        await self.wait_until_ready()

    async def on_message(self, message: disnake.Message):
        if message.author == self.user:
            return

        try:
            if not db.search(Guild.id == message.guild.id):
                db.insert(
                    {
                        'id': message.guild.id, 
                        'prefix': None, 
                        'filter_profanity': False,
                        'greet_members': False,
                        'greet_message': None,
                        'default_commands_channel': None
                    }
                )
        except AttributeError:
            pass

        if (
            not await check_if_swore(message)
            and not await check_if_frozen(message)
            and not await check_if_jailed(message)
        ):
            guild = get_guild_dict(message.guild.id)

            if (
                guild['default_commands_channel']
                and message.channel.id == guild['default_commands_channel']
                or not guild['default_commands_channel']
            ):
                await self.process_commands(message)

    async def on_message_delete(self, message: disnake.Message):
        global snipeables
        snipeables.append(message)
        await asyncio.sleep(25)
        snipeables.remove(message)

    async def on_member_join(self, member: disnake.Member):
        guild = get_guild_dict(member.guild.id)
        if guild and guild['greet_members']:
            await member.send(guild['greet_message'])


# Setting up the fundamentals.
uvloop.install()
bot = Bot()
bot.topggpy = topgg.DBLClient(bot, tokens['topggpy'])

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
    async def on_command_error(self, ctx: commands.Context, error: Any):
        if hasattr(ctx.command, 'on_error'):
            return

        cog = ctx.cog
        if cog and cog._get_overridden_method(cog.cog_command_error) is not None:
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

        elif isinstance(error, commands.errors.CommandError):
            await ctx.reply(embed=generate_error_embed(title='A command error occured!', description=error, footer_avatar=ctx.author.avatar))

        elif isinstance(error, commands.errors.CheckFailure):
            pass

        elif isinstance(error, disnake.errors.NotFound):
            pass

        elif isinstance(error, disnake.errors.Forbidden):
            await ctx.reply(embed=generate_error_embed(title='The command couldn\'t be processed.', description='Either I\'m missing the required permissions or I just need to be at a higher position in the role hierarchy.', footer_avatar=ctx.author.avatar))

        else:
            embed = (
                generate_error_embed(
                    title='An internal error occured.', 
                    description='If you think that it shouldn\'t happen, then try opening a ticket in our [support server](https://discord.gg/6GNgcu7hjn) and describe the issue. We\'ll try our best to demolish the bug for you (if it\'s there).', 
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
    async def on_slash_command_error(self, inter: disnake.ApplicationCommandInteraction, error):
        if isinstance(error, commands.NoPrivateMessage):
            await inter.response.send_message(embed=generate_error_embed(title='This command can\'t be used in DMs.', description=f'The command `{inter.data.name}` has been configured to only be executed in servers, not DM channels.', footer_avatar=inter.author.avatar), ephemeral=True)


# Chill commands.
class Chill(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(
        name='avatar', 
        help='Shows a member\'s Discord avatar.'
    )
    @commands.guild_only()
    async def avatar(self, ctx: commands.Context, member: disnake.Member=None):
        if not member:
            member = ctx.message.author

        embed = (
            disnake.Embed(
                title='Here\'s what I found!', 
                color=accent_color['primary']
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
    async def _avatar(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member=None):
        if not member:
            member = inter.author

        embed = (
            disnake.Embed(
                title='Here\'s what I found!', 
                color=accent_color['primary']
            ).set_image(
                url=member.avatar
            ).set_footer(
                text=generate_random_footer(),
                icon_url=inter.author.avatar
            )
        )
        await inter.send(embed=embed)

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
            round(time.time() - startup_data['obj']))))

        embed = (
            disnake.Embed(
                color=accent_color['primary']
            ).add_field(
                name='System Latency', 
                value=f'{system_latency}ms [{self.bot.shard_count} shard(s)]', 
                inline=False
            ).add_field(
                name='API Latency',
                value=f'{api_latency}ms'
            ).add_field(
                name='Startup Time', 
                value=startup_data['str'], 
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
    async def _ping(self, inter: disnake.ApplicationCommandInteraction):
        system_latency = round(self.bot.latency * 1000)

        start_time = time.time()
        await inter.send('Testing overall speed...')
        end_time = time.time()

        api_latency = round((end_time - start_time) * 1000)
        uptime = str(datetime.timedelta(seconds=int(
            round(time.time() - startup_data['obj']))))

        embed = (
            disnake.Embed(
                color=accent_color['primary']
            ).add_field(
                name='System Latency', 
                value=f'{system_latency}ms [{self.bot.shard_count} shard(s)]', 
                inline=False
            ).add_field(
                name='API Latency',
                value=f'{api_latency}ms'
            ).add_field(
                name='Startup Time', 
                value=startup_data['str'], 
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
        await inter.edit_original_message(content=None, embed=embed)

    @commands.command(
        name='vote', 
        help='Vote for me on Top.gg!'
    )
    @commands.guild_only()
    async def vote(self, ctx: commands.Context):
        vote = await check_if_voted(ctx.author.id)

        if vote is False:
            embed = (
                disnake.Embed(
                    title=':military_medal: Voting Section', 
                    description='Hey! Looks like you haven\'t voted for me today. If you\'re free, then be sure to check the links below to vote for me on Top.gg! It really helps my creator to get energetic and encourages him to launch more updates.',
                    color=accent_color['primary']
                ).set_footer(
                    text=generate_random_footer(),
                    icon_url=ctx.author.avatar
                )
            )
            await ctx.reply(embed=embed, view=VoteCommandView())
            
        elif vote is True:
            await ctx.reply('You have already voted for me today, yay!')

    @commands.slash_command(
        name='vote',
        description='Vote for me on Top.gg!'
    )
    @commands.guild_only()
    async def _vote(self, inter: disnake.ApplicationCommandInteraction):
        vote = await check_if_voted(inter.author.id)
        
        if vote is False:
            embed = (
                disnake.Embed(
                    title=':military_medal: Voting Section', 
                    description='Hey! Looks like you haven\'t voted for me today. If you\'re free, then be sure to check the links below to vote for me on Top.gg! It really helps my creator to get energetic and encourages him to launch more updates.',
                    color=accent_color['primary']
                ).set_footer(
                    text=generate_random_footer(),
                    icon_url=inter.author.avatar
                )
            )
            await inter.send(embed=embed, view=VoteCommandView())
            
        elif vote is True:
            await inter.send('You have already voted for me today, yay!', ephemeral=True)

# Casual commands.
class Inspection(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(
        name='senddm', 
        help='Helps to send DMs to specific users.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def senddm(self, ctx: commands.Context, user: disnake.User, *, message: str):
        if not user == ctx.author:
            embed = (
                disnake.Embed(
                    title=f'{ctx.author.display_name} > {message}',
                    color=accent_color['primary']
                )
            )
            await user.send(embed=embed)
            await ctx.send(f'{ctx.author.mention} your message has been sent!')
            await ctx.message.delete()

        else:
            await ctx.send('You can\'t message yourself!')

    @commands.slash_command(
        name='senddm',
        description='Helps to send DMs to specific users.',
        options=[
            Option("user", "Mention your desired user.", OptionType.user, required=True),
            Option("message", "Type the message that you wanna send to the given user.", OptionType.string, required=True)
        ]
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def _senddm(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, *, message: str):
        if not user == inter.author:
            embed = (
                disnake.Embed(
                    title=f'{inter.author.display_name} > {message}',
                    color=accent_color['primary']
                )
            )
            await user.send(embed=embed)
            await inter.send(f'Your message has been sent!', ephemeral=True)

        else:
            await inter.send('You can\'t message yourself!', ephemeral=True)

    @commands.command(
        name='userinfo', 
        help='Shows all important information on a user.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def userinfo(self, ctx: commands.Context, user: disnake.Member=None):
        if not user:
            user = ctx.author

        qr_file_name, qr_file = generate_qr_code(id=user.id, text_to_embed=f'https://discordapp.com/users/{user.id}/')

        embed = (
            disnake.Embed(
                title=f'{user}',
                color=accent_color['primary']
            )
        ).add_field(
            name='Status', 
            value=user.status
        ).add_field(
            name='Birth', 
            value=user.created_at.strftime("%b %d, %Y")
        ).add_field(
            name='On Mobile', 
            value=user.is_on_mobile()
        ).add_field(
            name='Race', 
            value='Bots, execute em!' if user.bot else 'Human'
        ).add_field(
            name='Roles', 
            value=len(user.roles)
        ).add_field(
            name='Position',
            value=user.top_role.mention
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

    @commands.slash_command(
        name='userinfo', 
        description='Shows all important information on a user.',
        options=[
            Option("user", "Mention your desired user.", OptionType.user)
        ]
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def _userinfo(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member=None):
        if not user:
            user = inter.author

        qr_file_name, qr_file = generate_qr_code(id=user.id, text_to_embed=f'https://discordapp.com/users/{user.id}/')

        embed = (
            disnake.Embed(
                title=f'{user}',
                color=accent_color['primary']
            )
        ).add_field(
            name='Status', 
            value=user.status
        ).add_field(
            name='Birth', 
            value=user.created_at.strftime("%b %d, %Y")
        ).add_field(
            name='On Mobile', 
            value=user.is_on_mobile()
        ).add_field(
            name='Race', 
            value='Bots, execute em!' if user.bot else 'Human'
        ).add_field(
            name='Roles', 
            value=len(user.roles)
        ).add_field(
            name='Position',
            value=user.top_role.mention
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
                icon_url=inter.author.avatar
            )
        except:
            embed.set_footer(
                text=generate_random_footer(),
                icon_url=inter.author.avatar
            )

        await inter.send(file=qr_file, embed=embed)
        
        if os.path.exists(qr_file_name):
            os.remove(qr_file_name)

    @commands.command(
        name='guildinfo', 
        help='Shows all important information on the current guild / server.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def guildinfo(self, ctx: commands.Context):
        guild = get_guild_dict(ctx.guild.id)
        embed = (
            disnake.Embed(
                color=accent_color['primary']
            )
        ).add_field(
            name='Birth',
            value=ctx.guild.created_at.strftime("%b %d, %Y")
        ).add_field(
            name='Owner',
            value=ctx.guild.owner.mention
        ).add_field(
            name='Region', 
            value=ctx.guild.region
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
            name='Prefix',
            value=prefix if not guild['prefix'] else guild['prefix']
        ).add_field(
            name='Identifier', 
            value=ctx.guild.id,
        ).set_thumbnail(
            url=ctx.guild.icon
        ).set_footer(
            text=generate_random_footer(),
            icon_url=ctx.author.avatar
        )
        await ctx.reply(embed=embed)

    @commands.slash_command(
        name='guildinfo', 
        description='Shows all important information on the current guild / server.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def _guildinfo(self, inter: disnake.ApplicationCommandInteraction):
        guild = get_guild_dict(inter.guild.id)
        embed = (
            disnake.Embed(
                color=accent_color['primary']
            )
        ).add_field(
            name='Birth',
            value=inter.guild.created_at.strftime("%b %d, %Y")
        ).add_field(
            name='Owner',
            value=inter.guild.owner.mention
        ).add_field(
            name='Region', 
            value=inter.guild.region
        ).add_field(
            name='Members', 
            value=inter.guild.member_count
        ).add_field(
            name='Roles', 
            value=len(inter.guild.roles)
        ).add_field(
            name='Channels', 
            value=len(inter.guild.channels)
        ).add_field(
            name='Prefix',
            value=prefix if not guild['prefix'] else guild['prefix']
        ).add_field(
            name='Identifier', 
            value=inter.guild.id,
        ).set_thumbnail(
            url=inter.guild.icon
        ).set_footer(
            text=generate_random_footer(),
            icon_url=inter.author.avatar
        )
        await inter.send(embed=embed)

    @commands.command(
        name='roleinfo', 
        help='Shows all important information related to a specific role.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def roleinfo(self, ctx: commands.Context, role: disnake.Role):
        embed = (
            disnake.Embed(
                title=f'Role Information: {role}', color=accent_color['primary']
            ).add_field(
                name='Birth', 
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
                name='Identifier', 
                value=f'`{role.id}`'
            ).set_footer(
                text=generate_random_footer(), 
                icon_url=ctx.author.avatar
            )
        )
        await ctx.reply(embed=embed)

    @commands.slash_command(
        name='roleinfo', 
        description='Shows all important information related to a specific role.',
        options=[
            Option("role", "Mention your desired role.", OptionType.role, required=True)
        ]
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def _roleinfo(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        embed = (
            disnake.Embed(
                title=f'Role Information: {role}', color=accent_color['primary']
            ).add_field(
                name='Birth', 
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
                name='Identifier', 
                value=f'`{role.id}`'
            ).set_footer(
                text=generate_random_footer(), 
                icon_url=inter.author.avatar
            )
        )
        await inter.send(embed=embed)

    @commands.command(
        name='audit', 
        help='Views the latest entries of the audit log in detail (limited to 100 entries).'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def audit(self, ctx: commands.Context, limit: int=5):
        if int(limit) > 70:
            await ctx.reply('Log limit has to be within 1 and 70.')

        else:
            embed = (
                disnake.Embed(
                    title='Audit Log', 
                    description=f'Showing the latest {limit} entries that were made in the audit log of {ctx.guild.name}.', 
                    color=accent_color['primary']
                ).set_footer(
                    text=generate_random_footer(), 
                    icon_url=ctx.author.avatar
                )
            )
            async for audit_entry in ctx.guild.audit_logs(limit=limit):
                embed.add_field(
                    name=f'- {audit_entry.action}', 
                    value=f'User: {audit_entry.user} | Target: {audit_entry.target}', 
                    inline=False
                )
            await ctx.reply(embed=embed)

    @commands.slash_command(
        name='audit', 
        description='Views the latest entries of the audit log in detail (limited to 100 entries).',
        options=[
            Option("limit", "The number of logs you wanna go through.", OptionType.integer)
        ]
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def _audit(self, inter: disnake.ApplicationCommandInteraction, limit: int=5):
        if int(limit) > 70:
            await inter.send('Log limit has to be within 1 and 70.')

        else:
            embed = (
                disnake.Embed(
                    title='Audit Log', 
                    description=f'Showing the latest {limit} entries that were made in the audit log of {inter.guild.name}.', 
                    color=accent_color['primary']
                ).set_footer(
                    text=generate_random_footer(), 
                    icon_url=inter.author.avatar
                )
            )
            async for audit_entry in inter.guild.audit_logs(limit=limit):
                embed.add_field(
                    name=f'- {audit_entry.action}', 
                    value=f'User: {audit_entry.user} | Target: {audit_entry.target}', 
                    inline=False
                )
            await inter.send(embed=embed)


# General moderation commands.
class GeneralMod(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(
        name='purge', 
        help='Clears messages within the given index.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def purge(self, ctx: commands.Context, amount: int=1):
        if amount > 200:
            await ctx.reply('Purges are limited to 200 messages per use!')
        else:
            amount += 1
            await ctx.channel.purge(limit=amount)

    @commands.command(
        name='purgeone',
        help='Purges a message by its identifier.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def purgeone(self, ctx: commands.Context, message_id: int):
        message = await ctx.channel.fetch_message(message_id)
        print(message)
        await message.delete()
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='ripplepurge', 
        help='Clears messages that are sent by a specific user within the given index.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def ripplepurge(self, ctx: commands.Context, member: disnake.Member, amount: int=2):
        if amount > 100:
            await ctx.reply('Ripple purges are limited to 100 messages per use!')
        else:
            await ctx.message.add_reaction(reaction_emoji)
            messages = await ctx.history(limit=amount).flatten()

            for message in messages:
                if message.author == member:
                    await message.delete()

    @commands.command(
        name='msgweb', 
        help='Enables a web trap to capture six messages sent by a specific user.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def msgweb(self, ctx: commands.Context, member: disnake.Member):
        await ctx.message.delete()

        if ctx.author == member:
            return await ctx.author.send('You can\'t trap yourself!')
            
        await ctx.author.send(f'A message web trap on **{member}** has been activated. You\'ll shortly receive the captured messages once the action is complete.')

        web = []
        for _ in range(6):
            web.append(await wait_for_message(member, check_if_member=True))

        embed = (
            disnake.Embed(
                title='Web Trap Retracted',
                description=f'All captured messages from {member} are listed below.',
                color=accent_color['primary']
            ).set_footer(
                text=generate_random_footer(),
                icon_url=ctx.author.avatar
            )
        )

        for message in web:
            embed.add_field(
                name=message.content,
                value=f'Sent in #{message.channel}',
                inline=False
            )

        await ctx.author.send(embed=embed)

    @commands.command(
        name='snipemsg',
        help='Snipes a recent message from the channel.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
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
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def jail(self, ctx: commands.Context, member: disnake.Member, *, reason: str='None.'):
        do_jail = False

        if member == self.bot.user:
            await ctx.reply('Why are you even trying to jail me?')

        elif member == ctx.author:
            await ctx.reply('You can\'t jail yourself!')

        elif (
            member.guild_permissions.administrator
            and ctx.author.guild_permissions.administrator
            or not member.guild_permissions.administrator
        ):
            do_jail = True

        else:
            await ctx.reply('You can\'t jail an admin!')

        if do_jail:
            jail_members.append([member.id, ctx.guild.id, reason, ctx.author.id])
            await ctx.send(f'You\'ve been captured! {member.mention} | Reason: {reason}')
            await ctx.message.delete()

    @commands.command(
        name='jailed', 
        help='Views jailed members.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def jailed(self, ctx: commands.Context):
        jail_has_member = False

        embed = (
            disnake.Embed(
                title='Now viewing the prison!', 
                color=accent_color['primary']
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

        if not jail_has_member:
            await ctx.reply('No members are inside the jail.')

        else:
            await ctx.reply(embed=embed)

    @commands.command(
        name='unjail', 
        help='Removes a member from jail.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def unjail(self, ctx: commands.Context, member: disnake.Member):
        for jail_member in jail_members:
            if jail_member[1] == ctx.guild.id and jail_member[0] == member.id:
                if member != ctx.author:
                    jail_members.remove(jail_member)
                    await ctx.message.add_reaction(reaction_emoji)

                else:
                    await ctx.reply('You can\'t free yourself!')

    @commands.command(
        name='block', 
        help='Blocks a user from chatting in a specific channel.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def block(self, ctx: commands.Context, member: disnake.Member, *, reason: str='No reason provided.'):
        if member == self.bot.user:
            await ctx.reply('Why are you even trying to block me?')

        elif member != ctx.author:
            await ctx.channel.set_permissions(member, send_messages=False)
            await ctx.send(f'You\'re now blocked from chatting, {member.mention} | Reason: {reason}')
            await ctx.message.delete()

        else:
            await ctx.reply("You can't block yourself!")

    @commands.command(
        name='unblock', 
        help='Unblocks a user.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def unblock(self, ctx: commands.Context, member: disnake.Member):
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='kick', 
        help='Kicks a member from server.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def kick(self, ctx: commands.Context, member: disnake.User, *, reason: str='No reason provided.'):
        await ctx.guild.kick(member, reason=reason)
        await ctx.send(f'**{member.name}** has been kicked! Reason: {reason}')
        await ctx.message.delete()

    @commands.command(
        name='ban', 
        help='Bans a member from server.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def ban(self, ctx: commands.Context, member: disnake.User, *, reason: str='No reason provided.'):
        await ctx.guild.ban(member, reason=reason)
        await ctx.send(f'**{member.name}** has been banned! Reason: {reason}')
        await ctx.message.delete()

    @commands.command(
        name='bans', 
        help='Shows a list of banned users in the server.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def bans(self, ctx: commands.Context):
        bans = await ctx.guild.bans()
        embed = (
            disnake.Embed(
                title='Now viewing banned members!', 
                color=accent_color['primary']
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
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def unban(self, ctx: commands.Context, member: disnake.User):
        await ctx.guild.unban(member)
        await ctx.reply(f'Member **{member.name}** has been unbanned!')

    @commands.command(
        name='timeout',
        help='Timeouts a member.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def deafen(self, ctx: commands.Context, member: disnake.Member, duration: int=30, *, reason: str='No reason provided.'):
        await member.timeout(duration=duration, reason=reason)
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='freeze', 
        help='Calms down chat.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def freeze(self, ctx: commands.Context):
        frozen_guilds.append([ctx.author.id, ctx.guild.id, ctx.message.channel.id])
        await ctx.send(f'**Chat was frozen by {ctx.author.mention}!**')
        await ctx.message.delete()

    @commands.command(
        name='thaw', 
        help='Removes frozen state from chat.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def thaw(self, ctx: commands.Context):
        for frozen_guild in frozen_guilds:
            if frozen_guild[1] == ctx.guild.id:
                frozen_guilds.remove(frozen_guild)
                await ctx.message.add_reaction(reaction_emoji)


# Voice moderation commands.
class VoiceMod(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(
        name='move',
        help='Moves a member from-to specific a voice channel.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def move(self, ctx: commands.Context, member: disnake.Member, *, channel: disnake.VoiceChannel | disnake.StageChannel):
        await member.move_to(channel)
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='mute',
        help='Server-mutes a member.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def mute(self, ctx: commands.Context, member: disnake.Member):
        await member.edit(mute=True)
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='deafen',
        help='Server-deafens a member.'
    )    
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def deafen(self, ctx: commands.Context, member: disnake.Member):
        await member.edit(deafen=True)
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='stopstage',
        help='Stops any unning stage instance in a given stage channel.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def stopstage(self, ctx: commands.Context, *, channel: disnake.StageChannel):
        try:
            instance = await channel.fetch_instance()
            await instance.delete()
            await ctx.message.add_reaction(reaction_emoji)

        except:
            await ctx.reply(f'This stage channel doesn\'t have any instances running.')


# Customization commands.
class Customization(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(
        name='mkinv', 
        help='Creates an invite code or link.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def makeinv(self, ctx: commands.Context, max_age: int=60, max_uses: int=1, *, reason: str='No reason provided.'):
        if not reason:
            reason = f'Inviter: {ctx.author.name}'

        invite = await ctx.channel.create_invite(max_age=max_age, max_uses=max_uses, reason=reason)
        qr_file_name, qr_file = generate_qr_code(id=ctx.author.id, text_to_embed=invite)
        value = 'Infinity' if invite.max_age == 0 else f'{invite.max_age} Seconds'

        embed = (
            disnake.Embed(
                title=f'An invite to #{invite.channel} was created!',
                color=accent_color['primary']
            ).add_field(
                name='Link', 
                value=invite
            ).add_field(
                name='Identifier', 
                value=f'`{invite.id}`'
            ).add_field(
                name='Lifetime', 
                value=f'{value} [{invite.max_uses} use(s)]',
                inline=False
            ).set_image(
                url=f'attachment://{qr_file_name}'
            ).set_footer(
                text=generate_random_footer(),
                icon_url=ctx.author.avatar
            )
        )

        await ctx.reply(file=qr_file, embed=embed)

        if os.path.exists(qr_file_name):
            os.remove(qr_file_name)

    @commands.command(
        name='invs', 
        help='Shows all active server invite codes.'
    )
    @commands.guild_only()
    @commands.has_any_role(lock_roles['moderator'], lock_roles['admin'])
    async def invites(self, ctx: commands.Context):
        invites = await ctx.guild.invites()
        embed = (
            disnake.Embed(
                title='Now viewing invite codes!', 
                color=accent_color['primary']
            ).set_footer(
                icon_url=ctx.author.avatar, 
                text=generate_random_footer()
            )
        )

        if not invites:
            await ctx.reply('No invite codes have been generated.')

        else:
            for invcount, invite in enumerate(invites):
                embed.add_field(
                    name=f'[{invcount}] {invite}', 
                    value=f'Uses: {invite.uses} | Inviter: {invite.inviter.name} | ID: `{invite.id}`', 
                    inline=False
                )
            await ctx.reply(embed=embed)

    @commands.command(
        name='rminv', 
        help='Removes a previously generated invite code or link.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def removeinv(self, ctx: commands.Context, id: str):
        invites = await ctx.guild.invites()
        for invite in invites:
            if invite.id == id:
                await invite.delete()
                await ctx.reply('Invite has been deleted.')
                
    @commands.command(
        name='mkrole', 
        help='Creates a role.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def makerole(self, ctx: commands.Context, *, name: str):
        await ctx.guild.create_role(name=name)
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='rmrole', 
        help='Removes an existing role.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def removerole(self, ctx: commands.Context, *, role: disnake.Role):
        await role.delete()
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='assignrole', 
        help='Assigns an existing role to a server member.', pass_context=True
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def assignrole(self, ctx: commands.Context, role: disnake.Role, member: disnake.Member):
        await member.add_roles(role)
        await ctx.reply(f'Role {role.mention} has been given to {member.mention}, peace! :partying_face:')

    @commands.command(
        name='nick',
        help='Changes the nickname of a member.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def nick(self, ctx: commands.Context, member: disnake.Member, *, new_nick: str):
        await member.edit(nick=new_nick)
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='mktextch', 
        help='Creates a text channel.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def mktextch(self, ctx: commands.Context, *, name: str):
        await ctx.guild.create_text_channel(name)
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='mkvoicech',
        help='Creates a voice channel.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def mkvoicech(self, ctx: commands.Context, *, name: str):
        await ctx.guild.create_voice_channel(name)
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='clonech',
        help='Clones a given channel.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def clonech(self, ctx: commands.Context, *, channel: disnake.TextChannel | disnake.VoiceChannel | disnake.StageChannel):
        await channel.clone()
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='removech', 
        help='Removes an existing server channel.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def removech(self, ctx: commands.Context, *, channel: disnake.TextChannel | disnake.VoiceChannel | disnake.StageChannel):
        await channel.delete()
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='mkthread',
        help='Creates a new thread in the current channel.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def mkthread(self, ctx: commands.Context, *, name: str):
        message = await ctx.send(f'Created thread **{name}**.')
        await ctx.channel.create_thread(name=name, message=message)

    @commands.command(
        name='rmthread',
        help='Removes an existing thread in the current channel.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def rmthread(self, ctx: commands.Context, *, thread: disnake.Thread):
        await thread.delete()
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='mkcategory',
        help='Creates a category channel.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def mkcategory(self, ctx: commands.Context, *, name: str):
        await ctx.guild.create_category(name)
        await ctx.message.add_reaction(reaction_emoji)


# Tweaks commands.
class Tweaks(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot 

    @commands.command(
        name='setprefix',
        help='Shows / changes the server\'s default command prefix.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def prefix(self, ctx: commands.Context, prefix: str=None):
        db.update({'prefix': prefix}, Guild.id == ctx.guild.id)
        await ctx.reply(f'Changed server prefix to `{prefix}`!')

    @commands.command(
        name='setgreeting',
        help='Toggles the greeting message which is sent to an incoming Discord user upon joining the server.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def greetings(self, ctx: commands.Context, *, greet_message: str=None):
        if greet_message:
            embed = (
                disnake.Embed(
                    title='Greetings enabled!',
                    description=f'`{greet_message}` will be sent to anyone who joins this server from now on. You can disable it by using this command without any arguments.',
                    color=accent_color['primary']
                ).set_footer(
                    text=generate_random_footer(),
                    icon_url=ctx.author.avatar
                )
            )
            db.update({'greet_members': True, 'greet_message': greet_message}, Guild.id == ctx.guild.id)
            await ctx.reply(embed=embed)
        else:
            db.update({'greet_members': False, 'greet_message': None}, Guild.id == ctx.guild.id)
            await ctx.reply('Greetings have been disabled.')

    @commands.command(
        name='setdefaultch',
        help='Sets a specific channel as the default for executing commands.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def bindch(self, ctx: commands.Context, *, channel: disnake.TextChannel=None):
        if channel:
            embed = (
                disnake.Embed(
                    title=f'#{channel.name} has been binded!',
                    description='Now you won\'t be able to execute commands outside this channel. To unbind, just type this command again without any arguments.',
                    color=accent_color['primary']
                ).set_footer(
                    text=generate_random_footer(),
                    icon_url=ctx.author.avatar
                )
            )

            db.update({'default_commands_channel': channel.id}, Guild.id == ctx.guild.id)
            await ctx.reply(embed=embed)
        
        else:
            guild = get_guild_dict(ctx.guild.id)
            
            if not guild['default_commands_channel']:
                await ctx.reply('No channel is binded with me in this server.')

            else:
                channel = self.bot.get_channel(guild['default_commands_channel'])
                db.update({'default_commands_channel': None}, Guild.id == ctx.guild.id)
                await ctx.reply(f'Unbinded **#{channel.name}** successfully!')

    @commands.command(
        name='toggleprofanityfilter',
        help='Toggles the profanity filter.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def profanityfilter(self, ctx: commands.Context):
        guild = get_guild_dict(ctx.guild.id)
        previous_value = guild['filter_profanity']
        db.update({'filter_profanity': not previous_value}, Guild.id == ctx.guild.id)
        await ctx.reply(f'Profanity filter has been toggled `{not previous_value}`.')

    @commands.command(
        name='config',
        help='Shows the server\'s configuration data in a JSON file format.'
    )
    @commands.guild_only()
    @commands.has_role(lock_roles['admin'])
    async def viewconfig(self, ctx: commands.Context):
        guild = get_guild_dict(ctx.guild.id)
        embed = (
            disnake.Embed(
                color=accent_color['primary']
            ).add_field(
                name='Current Configuration',
                value=f'```json\n{json.dumps(guild, indent=4)}\n```'
            )
        )
        await ctx.reply(embed=embed)


# Music commands.
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
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop):
        loop = loop or asyncio.get_event_loop()

        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
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
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
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


# Base class for interacting with the Spotify API.
class Spotify:
    @classmethod
    def get_track_id(self, track: Any):
        track = sp.track(track)
        return track["id"]

    @classmethod
    def get_playlist_track_ids(self, playlist_id: Any):
        ids = []
        playlist = sp.playlist(playlist_id)

        for item in playlist['tracks']['items']:
            track = item['track']
            ids.append(track['id'])

        return ids

    @classmethod
    def get_album(self, album_id: Any):
        album = sp.album_tracks(album_id)
        return [item["id"] for item in album['items']]

    @classmethod
    def get_album_id(self, id: Any):
        return sp.album(id)

    @classmethod
    def get_track_features(self, id: Any):
        meta = sp.track(id)
        album = meta['album']['name']
        artist = meta['album']['artists'][0]['name']
        return f"{artist} - {album}"


# Functions / coroutines (for using within music commands and classes only).
def get_queue_embed(ctx: commands.Context, page: int=1):
    items_per_page = 10
    pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)

    start = (page - 1) * items_per_page
    end = start + items_per_page

    queue = ''.join(
        '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start)
    )

    embed = (
        disnake.Embed(
            description='**{} tracks:**\n\n{}'.format(len(ctx.voice_state.songs), queue)
        ).set_footer(
            text='Viewing page {}/{}'.format(page, pages)
        )
    )
    return embed


# Views (static / dynamic, for music commands).
class NowCommandView(disnake.ui.View):
    def __init__(self, url: str, views: str, likes: str, timeout: float=10):
        super().__init__(timeout=timeout)

        self.add_item(disnake.ui.Button(label='Redirect', url=url))
        self.add_item(disnake.ui.Button(label=f'{int(views):,} Views', style=disnake.ButtonStyle.grey))
        self.add_item(disnake.ui.Button(label=f'{int(likes):,} Likes', style=disnake.ButtonStyle.grey))

class PlayCommandView(disnake.ui.View):
    def __init__(self, url: str, timeout: float=10):
        super().__init__(timeout=timeout)
    
        self.add_item(disnake.ui.Button(label='Redirect', url=url))

class QueueView(disnake.ui.View):
    def __init__(self, ctx: commands.Context, timeout: float=30):
        super().__init__(timeout=timeout)
        self.ctx = ctx

    @disnake.ui.button(label='Clear Queue', style=disnake.ButtonStyle.danger)
    async def clear(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        self.ctx.voice_state.songs.clear()
        await interaction.response.edit_message(
            content='The queue has been cleared.',
            embed=None,
            view=None
        )
        await interaction.response.delete(delay=5)

    @disnake.ui.button(label='Shuffle', style=disnake.ButtonStyle.gray)
    async def shuffle(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        self.ctx.voice_state.songs.shuffle()
        await interaction.response.edit_message(
            content='The queue has been shuffled!',
            embed=get_queue_embed(self.ctx, page=1),
            view=None
        )


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
                color=accent_color['primary']
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
    def __getitem__(self, item: Any):
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


# Music commands.
class Music(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot
        self.voice_states = {}

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
            return await ctx.author.request_to_speak()

        ctx.voice_state.voice = await destination.connect()
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='summon', 
        help='Summons Veron1CA to a particular voice channel.'
    )
    @commands.guild_only()
    async def _summon(self, ctx: commands.Context, *, channel: disnake.VoiceChannel=None):
        destination = channel or ctx.author.voice.channel
        
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)

        ctx.voice_state.voice = await destination.connect()
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='leave', 
        help='Clears the queue and leaves the voice channel.'
    )
    @commands.guild_only()
    async def _leave(self, ctx: commands.Context):
        if not ctx.voice_state.voice:
            return await ctx.reply('I am not connected to any voice channel.')

        if not ctx.author.voice:
            return await ctx.reply('You are not in the same voice channel as mine.')

        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='volume', 
        help='Sets the volume of the player.'
    )
    @commands.guild_only()
    async def _volume(self, ctx: commands.Context, *, volume: int=None):
        vote = await check_if_voted(ctx.author.id)

        if (vote is None) or (vote is True):
            if not ctx.voice_state.is_playing:
                return await ctx.reply('There\'s nothing being played at the moment.')

            if not volume:
                embed = (
                    disnake.Embed(
                        title=f'Current Volume: {ctx.voice_state.current.source.volume * 100}%',
                        color=accent_color['primary']
                    ).set_footer(
                        text=generate_random_footer(),
                        icon_url=ctx.author.avatar
                    )
                )
                return await ctx.reply(embed=embed)

            if 0 >= volume >= 100:
                return await ctx.reply('Volume must be between 0 and 100 to execute the command.')

            ctx.voice_state.current.source.volume = volume / 100
            await ctx.reply(f'Volume of the player is now set to **{volume}%**')

        else:
            embed = (
                disnake.Embed(
                    title='Whoops! This command is locked.',
                    description=f'By voting for me on Top.gg, you\'ll unlock `{ctx.command}` and all other locked commands for 12 hours.',
                    color=accent_color['error']
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
        if not ctx.voice_state.voice:
            return await ctx.reply('I am not connected to any voice channel.')

        if not ctx.author.voice:
            return await ctx.reply('You are not in the same voice channel as mine.')
        
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='resume', 
        help='Resumes a currently paused song.'
    )
    @commands.guild_only()
    async def _resume(self, ctx: commands.Context):
        if not ctx.voice_state.voice:
            return await ctx.reply('I am not connected to any voice channel.')

        if not ctx.author.voice:
            return await ctx.reply('You are not in the same voice channel as mine.')

        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='stop', 
        help='Stops playing song and clears the queue.'
    )
    @commands.guild_only()
    async def _stop(self, ctx: commands.Context):
        if not ctx.voice_state.voice:
            return await ctx.reply('I am not connected to any voice channel.')

        if not ctx.author.voice:
            return await ctx.reply('You are not in the same voice channel as mine.')

        ctx.voice_state.songs.clear()

        if ctx.voice_state.is_playing:
            if ctx.voice_state.loop:
                ctx.voice_state.loop = not ctx.voice_state.loop

            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='skip', 
        help='Vote to skip a song. The requester can automatically skip.'
    )
    @commands.guild_only()
    async def _skip(self, ctx: commands.Context):
        if not ctx.voice_state.is_playing:
            return await ctx.reply('Not playing any music right now, so no skipping for you.')

        if ctx.voice_state.loop:
            return await ctx.reply(f'Unable to skip as looping is enabled. Try using `{prefix}loop` to turn it off.')

        voter = ctx.author

        if voter == ctx.voice_state.current.requester:
            await ctx.message.add_reaction(reaction_emoji)
            ctx.voice_state.skip()

        elif voter.id not in ctx.voice_state.skip_votes:
            ctx.voice_state.skip_votes.add(voter.id)
            total_votes = len(ctx.voice_state.skip_votes)

            if total_votes >= 3:
                await ctx.message.add_reaction(reaction_emoji)
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
            return await ctx.reply('The queue is empty.')

        embed = get_queue_embed(ctx, page=page)
        await ctx.reply(embed=embed, view=QueueView(ctx))

    @commands.command(
        name='rmqueue',
        help='Removes a song from the queue at a given index.'
    )
    @commands.guild_only()
    async def _rmqueue(self, ctx: commands.Context, index: int):
        if not ctx.voice_state.voice:
            return await ctx.reply('I am not connected to any voice channel.')

        if not ctx.author.voice:
            return await ctx.reply('You are not in the same voice channel as mine.')

        if len(ctx.voice_state.songs) == 0:
            return await ctx.reply('The queue is empty, so nothing to be removed.')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction(reaction_emoji)

    @commands.command(
        name='loop', 
        help='Enables no-timeout looping for music playback.'
    )
    @commands.guild_only()
    async def _loop(self, ctx: commands.Context):
        vote = await check_if_voted(ctx.author.id)

        if (vote is None) or (vote is True):
            if not ctx.voice_state.is_playing:
                return await ctx.reply('There\'s nothing being played at the moment.')

            ctx.voice_state.loop = not ctx.voice_state.loop
            embed = (
                disnake.Embed(
                    title='Looping right now!' if ctx.voice_state.loop else 'Looping stopped.',
                    color=accent_color['primary']
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
                    color=accent_color['error']
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
    async def _play(self, ctx: commands.Context, *, search: str=None):
        enqueueing_embed = (
            disnake.Embed(
                title='Enqueueing...',
                color=accent_color['primary']
            ).set_footer(
                text=generate_random_footer(),
                icon_url=ctx.author.avatar
            )
        )

        if not ctx.voice_state.voice:
            await ctx.invoke(self._join)

        if not search:
            await ctx.reply('Type the name of a song, or anything! I\'m listening.')
            search = (await wait_for_message(ctx.author, check_if_member=True)).content
            
        async def put_song_to_voice_state(ctx: commands.Context, search: str, send_embed: bool=True):
            try:
                source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                await ctx.reply('An error occurred while processing this request: {}'.format(str(e)))
            else:
                song = Song(source)
                embed = (
                    disnake.Embed(
                        title=f'Enqueued {song.source.title} from YouTube.',
                        color=accent_color['primary']
                    ).set_footer(
                        text=generate_random_footer(),
                        icon_url=ctx.author.avatar
                    )
                )
                await ctx.voice_state.songs.put(song)

                if send_embed:
                    await ctx.reply(embed=embed, view=PlayCommandView(url=song.source.url))

        async with ctx.typing():
            if "https://open.spotify.com/playlist/" in search or "spotify:playlist:" in search:
                ids = Spotify.get_playlist_track_ids(search)
                tracks = []

                for i in range(len(ids)):
                    track = Spotify.get_track_features(ids[i])
                    tracks.append(track)

                sent_embed = await ctx.reply(embed=enqueueing_embed)

                for track in tracks:
                    await put_song_to_voice_state(ctx, track, send_embed=False)

                embed = (
                    disnake.Embed(
                        title=f'{len(tracks)} tracks have been queued!',
                        description=f'You can view the queue of songs imported from the playlist by using the `{prefix}queue` command.',
                        color=accent_color['primary']
                    ).set_footer(
                        text=generate_random_footer(),
                        icon_url=ctx.author.avatar
                    )
                )
                await sent_embed.edit(embed=embed)


            elif "https://open.spotify.com/album/" in search or "spotify:album:" in search:
                ids = Spotify.get_album(search)
                tracks = []

                for i in range(len(ids)):
                    track = Spotify.get_track_features(ids[i])
                    tracks.append(track)

                sent_embed = await ctx.reply(embed=enqueueing_embed)

                for track in tracks:
                    await put_song_to_voice_state(ctx, track, send_embed=False)

                embed = (
                    disnake.Embed(
                        title=f'{len(tracks)} tracks have been queued!',
                        description=f'You can view the queue of song imported from the album by using the `{prefix}queue` command.',
                        color=accent_color['primary']
                    ).set_footer(
                        text=generate_random_footer(),
                        icon_url=ctx.author.avatar
                    )
                )
                await sent_embed.edit(embed=embed)

            elif "https://open.spotify.com/track/" in search or "spotify:track:" in search:
                id = Spotify.get_track_id(search)
                track = Spotify.get_track_features(id)
                await put_song_to_voice_state(ctx, track)

            else:
                await put_song_to_voice_state(ctx, search)

    @commands.command(
        name='playrich',
        help='Fetches your Spotify rich presence data and enqueues the song that you\'re currently listening to.'
    )
    async def _playrich(self, ctx: commands.Context):
        for activity in ctx.author.activities:
            if isinstance(activity, disnake.Spotify):
                track = Spotify.get_track_features(activity.track_id)

                if not ctx.voice_state.voice:
                    await ctx.invoke(self._join)

                async with ctx.typing():
                    try:
                        source = await YTDLSource.create_source(ctx, track, loop=self.bot.loop)
                    except YTDLError as e:
                        await ctx.reply('An error occurred while processing this request: {}'.format(str(e)))
                    else:
                        song = Song(source)
                        embed = (
                            disnake.Embed(
                                title=f'Enqueued {song.source.title} from YouTube.',
                                color=activity.color
                            ).set_image(
                                url=activity.album_cover_url
                            ).set_footer(
                                text=f'Cover of the {activity.album} album by {activity.artist} on Spotify.',
                                icon_url=ctx.author.avatar
                            )
                        )
                        await ctx.voice_state.songs.put(song)
                        await ctx.reply(embed=embed, view=PlayCommandView(url=song.source.url))


    @_join.before_invoke
    @_play.before_invoke
    @_playrich.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError('You are not connected to my voice channel.')

        if (
            ctx.voice_client
            and ctx.voice_client.channel != ctx.author.voice.channel
        ):
            raise commands.CommandError('I\'m already in a voice channel.')


# Developer commands/tools.
class Developer(commands.Cog):
    def __init__(self, bot: commands.AutoShardedBot):
        self.bot = bot

    @commands.command(
        name='close', 
        help='Closes the connection to Discord.'
    )
    @commands.check(is_developer)
    async def logout(self, ctx: commands.Context):
        await ctx.message.add_reaction(reaction_emoji)
        await self.bot.close()    


# A minimalistic API for viewing the system status.
app = Flask(__name__)

@app.route('/')
def home():
    return """
        <div class="container">
            <h1>""" + bot.user.name + """ is now live.</h1>
            <p>Perform a <code>GET (this_url)/ping</code> request to interact!</p>
        </div>

        <style>
            @import url('https://fonts.googleapis.com/css2?family=Raleway:wght@700&display=swap');

            body {
                margin: 0;
                padding: 0;
                background-color: #ffffff;
            }

            .container {
                font-family: 'Raleway', sans-serif;
                height: 15em;
                position: relative;
            }

            .container h1 {
                font-weight: 700;
                color: #283048;
                position: absolute;
                top: 50%;
                left: 50%;
                margin-right: -50%;
                transform: translate(-50%, -50%);
            }

            .container p {
                color: #28304890;
                position: absolute;
                top: 70%;
                left: 50%;
                margin-right: -50%;
                transform: translate(-50%, -50%);
            }

            .container p code {
                padding: 5px 15px;
                color: #ffffff;
                background: #28304890;
                border-radius: .2rem;
            }
        </style>
    """

@app.route('/ping')
def ping():
    ping_dict = {
        'latency': round(bot.latency * 1000),
        'uptime': int(round(time.time() - startup_data['obj'])),
        'last_restart': startup_data['str']
    }
    return jsonify(ping_dict)

def run():
    app.run(host='0.0.0.0', port=8080, debug=False)
    
cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

t = Thread(target=run)
t.start()


# Add available cogs.
bot.add_cog(ExceptionHandler(bot))
bot.add_cog(Chill(bot))
bot.add_cog(Inspection(bot))
bot.add_cog(GeneralMod(bot))
bot.add_cog(VoiceMod(bot))
bot.add_cog(Customization(bot))
bot.add_cog(Tweaks(bot))
bot.add_cog(Music(bot))
bot.add_cog(Developer(bot))


# Run the bot.
bot.run(tokens['discord'])