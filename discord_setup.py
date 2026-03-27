"""
One-time Discord server setup script.
Run this ONCE to create all the roles, categories and channels in your server.

Usage:
    python discord_setup.py

Requires:
    BOT_TOKEN  = your Discord bot token (set in .env)
    GUILD_ID   = your server ID (set in .env)
"""
import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GUILD_ID  = os.getenv("GUILD_ID", "")

BASE = "https://discord.com/api/v10"
HEADERS = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json",
}


async def api(method: str, path: str, **kwargs):
    async with httpx.AsyncClient() as client:
        resp = await client.request(method, BASE + path, headers=HEADERS, **kwargs)
        if resp.status_code == 429:
            await asyncio.sleep(resp.json().get("retry_after", 1))
            return await api(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.text else {}


async def main():
    if not BOT_TOKEN or not GUILD_ID:
        print("ERROR: Set BOT_TOKEN and GUILD_ID in your .env file first.")
        sys.exit(1)

    print("Setting up Discord server...")

    # ── Roles ──────────────────────────────────────────────────────────────
    roles_to_create = [
        {"name": "👑 Owner",   "color": 0xFFD700, "hoist": True, "position": 10},
        {"name": "⚙️ Staff",   "color": 0x5865F2, "hoist": True, "position": 9},
        {"name": "💎 Premium", "color": 0x00B0F4, "hoist": True, "position": 8},
        {"name": "🆓 Free",    "color": 0x57F287, "hoist": True, "position": 7},
    ]
    role_ids = {}
    for r in roles_to_create:
        role = await api("POST", f"/guilds/{GUILD_ID}/roles", json={
            "name": r["name"], "color": r["color"], "hoist": r["hoist"]
        })
        role_ids[r["name"]] = role["id"]
        print(f"  Created role: {r['name']}")
        await asyncio.sleep(0.5)

    premium_role = role_ids.get("💎 Premium")

    # Permission overwrite helpers
    def deny_everyone():
        return [{"id": GUILD_ID, "type": 0, "allow": "0", "deny": "1024"}]

    def allow_role(role_id):
        return [
            {"id": GUILD_ID,  "type": 0, "allow": "0",    "deny": "1024"},
            {"id": role_id,   "type": 0, "allow": "1024", "deny": "0"},
        ]

    # ── Categories ─────────────────────────────────────────────────────────
    async def make_category(name: str, overwrites=None) -> str:
        cat = await api("POST", f"/guilds/{GUILD_ID}/channels", json={
            "name": name, "type": 4,
            "permission_overwrites": overwrites or [],
        })
        print(f"  Created category: {name}")
        await asyncio.sleep(0.3)
        return cat["id"]

    async def make_channel(name: str, parent_id: str, overwrites=None, topic: str = "") -> str:
        ch = await api("POST", f"/guilds/{GUILD_ID}/channels", json={
            "name": name, "type": 0, "parent_id": parent_id,
            "topic": topic,
            "permission_overwrites": overwrites or [],
        })
        print(f"    Created #  {name}")
        await asyncio.sleep(0.3)
        return ch["id"]

    # INFO category — public
    info_id = await make_category("📢 INFO")
    await make_channel("rules",         info_id, topic="Server rules")
    await make_channel("announcements", info_id, topic="Server announcements")
    await make_channel("upcoming-drops", info_id, topic="Upcoming Nike SNKRS & limited releases")

    # MONITORS category — Premium only
    mon_id = await make_category("🤖 MONITORS", allow_role(premium_role) if premium_role else [])
    await make_channel("amazon-deals",   mon_id, allow_role(premium_role) if premium_role else [], topic="Amazon coupons, deals & restocks")
    await make_channel("bestbuy-alerts", mon_id, allow_role(premium_role) if premium_role else [], topic="Best Buy price drops & restocks")
    await make_channel("walmart-deals",  mon_id, allow_role(premium_role) if premium_role else [], topic="Walmart Rollback deals & restocks")
    await make_channel("target-deals",   mon_id, allow_role(premium_role) if premium_role else [], topic="Target Circle deals & restocks")
    await make_channel("footlocker-alerts", mon_id, allow_role(premium_role) if premium_role else [], topic="Foot Locker / Champs shoe restocks")
    await make_channel("nike-snkrs",     mon_id, allow_role(premium_role) if premium_role else [], topic="Nike SNKRS live drops & restocks")
    await make_channel("all-alerts",     mon_id, allow_role(premium_role) if premium_role else [], topic="All monitors in one feed")

    # COMMUNITY category — public
    comm_id = await make_category("💬 COMMUNITY")
    await make_channel("general",      comm_id, topic="General chat")
    await make_channel("cops-pickups", comm_id, topic="Share your purchases!")
    await make_channel("help",         comm_id, topic="Get help from staff")

    print("\n✅ Server setup complete! Now add the webhook URLs to your .env file.")
    print("   Each #channel → Edit Channel → Integrations → Webhooks → New Webhook → Copy URL")


if __name__ == "__main__":
    asyncio.run(main())
