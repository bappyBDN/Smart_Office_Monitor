import discord
from discord.ext import commands, tasks
import google.generativeai as genai
import aiohttp
import os
import traceback
from dotenv import load_dotenv

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

_raw_channel_id = os.getenv("ALERT_CHANNEL_ID")
if not _raw_channel_id or not _raw_channel_id.strip().isdigit():
    raise RuntimeError(
        "ALERT_CHANNEL_ID is missing or invalid in .env. "
        "It must be a plain integer (right-click the channel in Discord -> Copy Channel ID, "
        "with Developer Mode enabled). No quotes, no server ID."
    )
ALERT_CHANNEL_ID = int(_raw_channel_id.strip())

BASE_URL = "http://127.0.0.1:8000"

# Gemini Setup
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Reused across the bot's lifetime instead of opening a new session per request.
http_session: aiohttp.ClientSession | None = None


async def fetch_api(endpoint: str):
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()
    try:
        async with http_session.get(f"{BASE_URL}{endpoint}", timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                return await response.json()
            print(f"[API] {endpoint} returned status {response.status}")
    except Exception:
        print(f"[API] Backend request to {endpoint} failed:")
        traceback.print_exc()
    return None


async def ask_gemini(prompt: str) -> str:
    system_instruction = (
        "You are an office assistant Discord bot. The boss asks you about the office lights and fans. "
        "Keep your response highly conversational, natural, friendly, and brief (max 2 sentences). "
        "Do not output raw JSON. "
    )
    try:
        response = await model.generate_content_async(system_instruction + prompt)
        return response.text
    except Exception:
        print("[Gemini] generate_content_async failed:")
        traceback.print_exc()
        return "Boss, my AI circuits are slightly fried right now!"


@bot.command(name="status")
async def check_status(ctx):
    devices = await fetch_api("/api/devices")
    if not devices:
        await ctx.send("API is unreachable! (backend down or not responding on port 8000)")
        return

    active = [f"{d['room']} ({d['name']})" for d in devices if d["status"] == "ON"]
    prompt = f"The following devices are currently ON: {active}. Give the boss a quick, friendly summary."
    reply = await ask_gemini(prompt)
    await ctx.send(reply)


@bot.command(name="room")
async def check_room(ctx, *, room_name: str):
    room_data = await fetch_api(f"/api/room/{room_name}")
    if not room_data or "error" in room_data:
        await ctx.send(f"I couldn't find a room named '{room_name}'. Try 'WorkRoom1' or 'DrawingRoom'.")
        return

    prompt = (
        f"Data for {room_data['room_name']}: {room_data['active_devices']['fans']} fans ON, "
        f"{room_data['active_devices']['lights']} lights ON. Drawing {room_data['total_power_watts']}W power. "
        f"Write a natural reply for the boss."
    )
    reply = await ask_gemini(prompt)
    await ctx.send(reply)


@bot.command(name="usage")
async def check_usage(ctx):
    devices = await fetch_api("/api/devices")
    if not devices:
        await ctx.send("API is unreachable!")
        return

    total_power = sum(d["power_draw"] for d in devices if d["status"] == "ON")
    estimated_kwh = round((total_power * 8) / 1000, 2)

    prompt = f"Total power right now is {total_power}W. Today's estimated usage is {estimated_kwh} kWh. Write a natural reply for the boss telling these stats."
    reply = await ask_gemini(prompt)
    await ctx.send(reply)


# --- Debug helper: force a test alert to confirm the pipeline works end-to-end ---
@bot.command(name="testalert")
@commands.has_permissions(administrator=True)
async def test_alert(ctx):
    try:
        channel = await bot.fetch_channel(ALERT_CHANNEL_ID)
        await channel.send("🚨 Test alert — if you see this, the channel ID and permissions are correct.")
        await ctx.send("Sent a test alert to the configured channel.")
    except discord.errors.NotFound:
        await ctx.send(f"❌ Channel ID {ALERT_CHANNEL_ID} not found — you likely copied the Server ID instead of the Channel ID.")
    except discord.errors.Forbidden:
        await ctx.send(f"❌ Bot lacks permission to post in channel {ALERT_CHANNEL_ID}. Grant it 'View Channel' + 'Send Messages'.")
    except Exception as e:
        await ctx.send(f"❌ Unexpected error: {e}")


@tasks.loop(seconds=3600)
async def discord_alert_system():
    alerts = await fetch_api("/api/alerts")
    print(f"[AlertLoop] Checked at loop tick. Alerts found: {alerts}")

    if not alerts:
        return

    try:
        channel = await bot.fetch_channel(ALERT_CHANNEL_ID)
        # /api/alerts now returns structured objects: {device_id, room, device_name, rule, message, timestamp}
        alert_messages = [a["message"] if isinstance(a, dict) else a for a in alerts]
        prompt = f"These alerts just triggered in the office: {alert_messages}. Write a proactive, slightly urgent Discord message asking if someone forgot to turn them off."
        alert_msg = await ask_gemini(prompt)
        await channel.send(f"🚨 **Alert** 🚨\n{alert_msg}")
        print("[AlertLoop] ✅ Alert sent to Discord!")

    except discord.errors.NotFound:
        print(f"[AlertLoop] ❌ Channel ID {ALERT_CHANNEL_ID} not found. You may have copied the Server ID instead of the Channel ID.")
    except discord.errors.Forbidden:
        print(f"[AlertLoop] ❌ Bot lacks permission to send messages in channel {ALERT_CHANNEL_ID}. Give it 'View Channel' and 'Send Messages'.")
    except Exception:
        print("[AlertLoop] ❌ Unexpected error:")
        traceback.print_exc()


@discord_alert_system.before_loop
async def before_alert_loop():
    # Ensures the gateway connection is fully ready before the first tick,
    # avoiding "not connected" errors on cold start.
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} with Gemini API active!')
    # Guard against on_ready firing multiple times on reconnect, which would
    # otherwise crash tasks.loop with "already launched" or spawn duplicate loops.
    if not discord_alert_system.is_running():
        discord_alert_system.start()


@bot.event
async def on_command_error(ctx, error):
    print(f"[CommandError] {ctx.command}: {error}")
    await ctx.send(f"⚠️ Something went wrong running that command: `{error}`")


bot.run(DISCORD_TOKEN)