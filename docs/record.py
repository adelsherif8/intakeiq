"""Record an IntakeIQ demo (drives the text flow; TTS audio still fires)."""
import asyncio
from playwright.async_api import async_playwright

URL = "http://localhost:8093/"
OUT = "/Users/adel/Desktop/GHAI/intakeiq/docs/video"
TURNS = ["I'm Sarah Johnson", "I need a teeth cleaning", "555 123 4567 and sarah@mail.com",
         "the afternoon one works"]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1180, "height": 820},
                                  record_video_dir=OUT,
                                  record_video_size={"width": 1180, "height": 820},
                                  device_scale_factor=2)
        page = await ctx.new_page()
        try:
            await page.goto(URL)
            await page.wait_for_timeout(1200)
            await page.click("text=Start call")
            await page.wait_for_selector(".msg.bot", timeout=20000)
            await page.wait_for_timeout(3000)
            for t in TURNS:
                await page.fill("#tin", t)
                await page.wait_for_timeout(500)
                await page.press("#tin", "Enter")
                await page.wait_for_timeout(6500)   # allow LLM + TTS to finish
            try:
                await page.wait_for_selector(".booking.show", timeout=15000)
            except Exception:
                pass
            await page.wait_for_timeout(3000)
        finally:
            await ctx.close()
            await b.close()
        print("recorded")


asyncio.run(main())
