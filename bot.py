import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import json
import os

TOKEN = os.getenv("TOKEN")  # Token bota z ENV
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # ID kanału z ENV
URL = "https://fatalis.soerpg.com/sub.php?page=onlinelist"
LIST_FILE = "lists.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

pinned_message = None

# ===== ZARZĄDZANIE LISTAMI =====
def load_lists():
    if os.path.exists(LIST_FILE):
        with open(LIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"friends": {}, "enemies": {}}

def save_lists(data):
    with open(LIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

lists = load_lists()

# ===== POBIERANIE ONLINE =====
def get_online_list():
    """Pobiera listę graczy online ze strony i ich levele."""
    r = requests.get(URL)
    soup = BeautifulSoup(r.text, "html.parser")

    players = {}
    rows = soup.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 2:
            name = cols[0].get_text(strip=True)
            lvl = cols[1].get_text(strip=True)
            if name and lvl.isdigit():
                players[name] = int(lvl)
    return players

# ===== AKTUALIZACJA PINNED =====
@tasks.loop(minutes=2)
async def update_online_list():
    global pinned_message
    channel = bot.get_channel(CHANNEL_ID)
    online = get_online_list()

    online_friends = []
    online_enemies = []

    for name, lvl in online.items():
        if name in lists["friends"]:
            old_lvl = lists["friends"][name]
            if old_lvl != lvl:
                if lvl > old_lvl:
                    await channel.send(f"🟢 Friend **{name}** zdobył lvl! ({old_lvl} → {lvl})")
                else:
                    await channel.send(f"🔴 Friend **{name}** stracił lvl! ({old_lvl} → {lvl})")
                lists["friends"][name] = lvl
                save_lists(lists)
            online_friends.append(f"{name} ({lvl})")

        if name in lists["enemies"]:
            old_lvl = lists["enemies"][name]
            if old_lvl != lvl:
                if lvl > old_lvl:
                    await channel.send(f"⚔️ Enemy **{name}** zdobył lvl! ({old_lvl} → {lvl})")
                else:
                    await channel.send(f"💀 Enemy **{name}** stracił lvl! ({old_lvl} → {lvl})")
                lists["enemies"][name] = lvl
                save_lists(lists)
            online_enemies.append(f"{name} ({lvl})")

    msg = (
        "📌 **Online List (auto-update)**\n\n"
        "👥 **Friends online:**\n" + ("\n".join(online_friends) if online_friends else "Brak") +
        "\n\n☠️ **Enemies online:**\n" + ("\n".join(online_enemies) if online_enemies else "Brak")
    )

    if pinned_message is None:
        pins = await channel.pins()
        for pin in pins:
            if pin.author == bot.user:
                pinned_message = pin
                break

    if pinned_message:
        await pinned_message.edit(content=msg)
    else:
        pinned_message = await channel.send(msg)
        await pinned_message.pin()

# ===== KOMENDY =====
@bot.command()
async def addfriend(ctx, *, name: str):
    online = get_online_list()
    lvl = online.get(name, 0)
    lists["friends"][name] = lvl
    save_lists(lists)
    await ctx.send(f"✅ Dodano **{name}** do listy znajomych (lvl {lvl}).")

@bot.command()
async def addenemy(ctx, *, name: str):
    online = get_online_list()
    lvl = online.get(name, 0)
    lists["enemies"][name] = lvl
    save_lists(lists)
    await ctx.send(f"✅ Dodano **{name}** do listy wrogów (lvl {lvl}).")

@bot.command()
async def removefriend(ctx, *, name: str):
    if name in lists["friends"]:
        del lists["friends"][name]
        save_lists(lists)
        await ctx.send(f"❌ Usunięto **{name}** z listy znajomych.")
    else:
        await ctx.send(f"⚠️ {name} nie jest na liście znajomych.")

@bot.command()
async def removeenemy(ctx, *, name: str):
    if name in lists["enemies"]:
        del lists["enemies"][name]
        save_lists(lists)
        await ctx.send(f"❌ Usunięto **{name}** z listy wrogów.")
    else:
        await ctx.send(f"⚠️ {name} nie jest na liście wrogów.")

@bot.command()
async def list(ctx):
    friends_list = ", ".join([f"{n} ({lvl})" for n, lvl in lists["friends"].items()]) if lists["friends"] else "Brak"
    enemies_list = ", ".join([f"{n} ({lvl})" for n, lvl in lists["enemies"].items()]) if lists["enemies"] else "Brak"

    await ctx.send(
        f"📜 **Aktualne listy:**\n\n👥 Friends: {friends_list}\n☠️ Enemies: {enemies_list}"
    )

# ===== START BOTA =====
@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")
    update_online_list.start()

bot.run(TOKEN)
