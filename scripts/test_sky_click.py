from playwright.sync_api import sync_playwright

listing = "https://news.sky.com/topic/internet-safety-6281/1"

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 720},
        locale="en-GB",
    )
    page = context.new_page()
    page.goto(listing, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    link = page.locator('a[href*="/story/"]').first
    print("href", link.get_attribute("href"))
    link.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)
    print("title", page.title())
    print("len", len(page.content()))
    browser.close()
