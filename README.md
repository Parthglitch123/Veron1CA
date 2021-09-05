# Veron1CA
<img src="https://i.imgur.com/oSyJaep.jpg"><br><br>
An open source Discord moderation bot with all-in-one server moderation and beat handling capabilties.

![GitHub](https://img.shields.io/github/license/hitblast/Veron1CA?color=blue&style=for-the-badge)
![GitHub Repo stars](https://img.shields.io/github/stars/hitblast/Veron1CA?color=blue&style=for-the-badge)
![GitHub watchers](https://img.shields.io/github/watchers/hitblast/Veron1CA?color=blue&style=for-the-badge)

## Getting to know...
Veron1CA is designed to be the collab of a Discord moderation bot and a chill music bot. It mainly focuses on next level server moderation, which can make customizing and controlling Discord servers a breeze! It's source is open as well, which means anybody can contribute to it if they spot a nasty bug in the code. We would like you to explore the powers of Veron1CA by yourself, as there's a lot of stuff out there waiting!

Learn more / invite Veron1CA from [the official website here!](https://hitblast.github.io/Veron1CA)
<br><br>

## Things to note...
Now that you've successfully added Veron1CA to your server, it's time for some key things to note down. The **default prefix** for accessing Veron1CA is `vrn.` in this case. Here's a bunch of stuff that you can do with it:
* Use `vrn.<command>` to run your desired command. As an example, you can use `vrn.ping` to get Veron1CA's latency.
* Use `vrn.help` to get into the help section.
* Use `vrn.help all` to get an entire list of commands that you can use.
* Use `vrn.help <command>` to get help regarding a specific command. For example, you can use `vrn.help ping` in order to get help for the ping command.

There's also another thing to consider in this case, and that's **role locking**. By default, Veron1CA's moderation and customization-based features are locked to specific roles. We have two unlockable ones to create here:
* `BotMod` - Assign this to the moderators of your server.
* `BotAdmin` - Assign this to the admininstrators of your server.

Keep in mind that being careless with any of these can cause chaotic results. Hope you will be able to do it and will have a good time playing with Veron1CA. 
<br><br>

## Self-hosting
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
TOKEN=your_token_here
DBL_TOKEN=your_topgg_token_here(optional)
OWNER_ID=your_Discord_ID_here
COMMAND_PREFIX=your_command_prefix_here
```

* Finally, install [FFmpeg](https://ffmpeg.org/) for your platform and run Veron1CA simply by using:
```bash
python3 main.py
```
<br>

## Contribution
As mentioned in an earlier statement, Veron1CA is open source, and if you feel like submitting your own ideas and improving the codebase, you can do that in the form of a pull request! We will check what you've done and maybe it will get added if it's good enough.
<br><br>

## Licence
<blockquote>
MIT License

Copyright (c) 2021 HitBlast

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
</blockquote>
