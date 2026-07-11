import asyncio
from playwright.async_api import async_playwright
URL = "http://localhost:8093/"
TURNS = ["I'm Sarah Johnson", "I need a teeth cleaning", "555 123 4567 and sarah@mail.com", "the afternoon one works"]


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1180, "height": 860}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(URL); await page.wait_for_timeout(1000)
        await page.click("text=Start call")
        await page.wait_for_selector(".msg.bot"); await page.wait_for_timeout(3000)
        for t in TURNS:
            await page.fill("#tin", t); await page.press("#tin", "Enter")
            await page.wait_for_timeout(6500)
        await page.wait_for_timeout(1500)
        await page.screenshot(path="/Users/adel/Desktop/GHAI/intakeiq/docs/shot-booked.png")
        print("shot done")
        await ctx.close(); await b.close()

asyncio.run(main())
