import asyncio
from playwright.async_api import async_playwright
import json


BASE = "https://www.unegui.mn"
START_URL = BASE + "/l-hdlh/l-hdlh-zarna/oron-suuts-zarna/"


async def get_total_pages(page):
    # бүх data-page attribute авах
    pages = await page.locator(
        "ul.number-list a.page-number"
    ).evaluate_all("els => els.map(e => e.dataset.page)")

    # None filter + int болгох
    page_numbers = [int(p) for p in pages if p is not None]

    return max(page_numbers)


async def scrape_page(page):
    adverts = page.locator(".advert__section")
    count = await adverts.count()

    data = []

    for i in range(count):
        ad = adverts.nth(i)

        price = await ad.locator(
            ".advert__content-price span"
        ).first.inner_text()

        title_el = ad.locator(".advert__content-title")
        title = await title_el.inner_text()
        link = await title_el.get_attribute("href")

        date = await ad.locator(
            ".advert__content-date"
        ).inner_text()

        place = await ad.locator(
            ".advert__content-place"
        ).inner_text()

        # data-id авах
        fav = ad.locator(".advert__content-favorite")
        ad_id = await fav.get_attribute("data-id")

        if link and link.startswith("/"):
            link = "https://www.unegui.mn" + link

        data.append({
            "id": ad_id,
            "title": title.strip(),
            "price": price.strip(),
            "date": date.strip(),
            "place": place.strip(),
            "link": link
        })

    return data


async def scrape_unegui():
    async with async_playwright() as p:
        # ЭНД АНХААР: 'await' нэмэх ёстой
        browser = await p.chromium.launch(headless=False)

        # Одоо browser объект бэлэн болсон тул new_context ажиллана
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("Хуудсыг ачаалж байна...")

        await page.goto(START_URL, wait_until="domcontentloaded")

        # Заруудыг агуулсан блокыг хүлээх
        await page.wait_for_selector(".advert__section")

        total_pages = await get_total_pages(page)
        print("Total pages:", total_pages)

        all_data = []

        # Заруудыг цуглуулах
        for pnum in range(1, total_pages + 1):
            url = START_URL if pnum == 1 else f"{START_URL}?page={pnum}"
            print("Scraping:", url)

            await page.goto(url)
            await page.wait_for_selector(".advert__section")

            page_data = await scrape_page(page)
            all_data.extend(page_data)

            # respectful delay
            await page.wait_for_timeout(1000)

        print(f"Нийт {len(all_data)} зар олдлоо.")
        # Үр дүнг хадгалах
        with open("unegui_data.json", "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_unegui())
