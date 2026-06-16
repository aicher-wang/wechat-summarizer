import asyncio
from playwright.async_api import async_playwright

async def html_to_pdf(html_path, pdf_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        # Convert Windows path to file:// URL
        file_url = "file:///" + html_path.replace("\\", "/").replace(":", ":")
        await page.goto(file_url)
        await page.pdf(
            path=pdf_path,
            format="A4",
            print_background=True,
            margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"}
        )
        await browser.close()
    print(f"PDF saved: {pdf_path}")

asyncio.run(html_to_pdf(
    "C:/Users/tengxiao.wang/Desktop/我爱一条柴_周报_2026-06-09~15.html",
    "C:/Users/tengxiao.wang/Desktop/我爱一条柴_周报_2026-06-09~15.pdf"
))
