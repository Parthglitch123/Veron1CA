# Veron1CA
An open source Discord moderation bot with all-in-one server moderation and beat handling capabilties.

![GitHub](https://img.shields.io/github/license/hitblast/Veron1CA?color=blue)
![GitHub Repo stars](https://img.shields.io/github/stars/hitblast/Veron1CA?color=blue)
![GitHub watchers](https://img.shields.io/github/watchers/hitblast/Veron1CA?color=blue)
![Discord Bots](https://top.gg/api/widget/upvotes/867998923250352189.svg)
<br><br>

## Features
Veron1CA is designed to be the collab of a Discord moderation bot and a chill music bot. It mainly focuses on next level server moderation, which can make customizing and controlling Discord servers a breeze! Here are a few things that come with it under the hood:

- Almost every necessary moderation command with some creative ones as well.
- Continuously updating codebase with regular maintenance.
- Built with modern, organized Python syntax.

Learn more / invite Veron1CA from [the official website here!](https://hitblast.github.io/Veron1CA)
<br><br>

## Notable Stuff
Now that you've successfully added Veron1CA to your server, it's time for some key things to note down. The **default prefix** for accessing Veron1CA is `vrn.` in this case. Here's a bunch of stuff that you can do with it:
* Use `vrn.<command>` to run your desired command. As an example, you can use `vrn.ping` to get Veron1CA's latency.
* Use `vrn.help` to get into the help section.
* Use `vrn.help <category>` to get an entire list of commands depending on which you choose.
* Use `vrn.help <command>` to get help regarding a specific command. For example, you can use `vrn.help ping` in order to get help for the ping command.

There's also another thing to consider in this case, and that's **role locking**. By default, Veron1CA's moderation and customization-based features are locked to specific roles. We have two unlockable ones to create here:
* `BotMod` - Assign this to the moderators of your server.
* `BotAdmin` - Assign this to the admininstrators of your server.

Keep in mind that being careless with any of these can cause chaotic results. Hope you will be able to do it and will have a good time playing with Veron1CA. 
<br><br>

## Self Hosting
* Clone the project. You can easily do this using:
```bash
git clone https://github.com/hitblast/Veron1CA.git
```

* Install [Poetry](https://python-poetry.org/) using Python's built-in package manager, [Pip](https://pypi.org/project/pip/).
```bash
python3 -m pip install -U poetry
```

* Navigate to the cloned directory and run the following command to install Veron1CA's dependencies.
```bash
python3 -m poetry install
```

* Alternatively, you can use the `requirements.txt` file to install the dependencies with [Pip](https://pypi.org/project/pip/) if you don't have [Poetry](https://python-poetry.org/).
```bash
python3 -m pip install -r requirements.txt
```

* Once it's done, create a `.env` file in the same directory and assign the values accordingly.
```
TOKEN=The token of your Discord bot
DBL_TOKEN=The token of your Top.gg bot
OWNER_ID=The ID number of your Discord profile
COMMAND_PREFIX=The command prefix of the bot
SPOTIFY_CLIENT_ID=The ID of your Spotify Developers application
SPOTIFY_CLIENT_SECRET=The secret of your Spotify Developers application
```

* Finally, install [FFmpeg](https://ffmpeg.org/) for your platform and run Veron1CA simply by using:
```bash
python3 main.py
```
<br>

## Contribution
Due to Veron1CA's open source nature, you can contribute to the code base pretty easily. Start off by [forking this repository](https://github.com/hitblast/Veron1CA) and creating a [pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests). We'll be happy to review it!
<br><br>

## Licensed under MIT
[Click here](LICENSE) to view the full document.
