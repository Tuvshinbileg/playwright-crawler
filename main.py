import asyncio
from playwright.async_api import async_playwright
import json

BASE = "https://www.unegui.mn"
START_URL = BASE + "/l-hdlh/l-hdlh-zarna/oron-suuts-zarna/"
MAX_CONCURRENT = 10  # 5–8 аюулгүй

# -------------------------
# Pagination max page авах
# -------------------------
async def get_total_pages(page):
    pages = await page.locator(
        "ul.number-list a.page-number"
    ).evaluate_all("els => els.map(e => e.dataset.page)")

    page_numbers = [int(p) for p in pages if p is not None]
    return max(page_numbers)


# -------------------------
# Нэг page scrape хийх
# -------------------------
async def scrape_page(context, page_number, semaphore):
    async with semaphore:
        page = await context.new_page()

        url = START_URL if page_number == 1 else f"{START_URL}?page={page_number}"
        print(f"Scraping page {page_number}")

        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_selector(".advert__section")

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

                fav = ad.locator(".advert__content-favorite")
                ad_id = await fav.get_attribute("data-id")

                if link and link.startswith("/"):
                    link = BASE + link

                data.append({
                    "id": ad_id,
                    "title": title.strip(),
                    "price": price.strip(),
                    "date": date.strip(),
                    "place": place.strip(),
                    "link": link
                })

            await page.close()
            return data

        except Exception as e:
            print(f"Error page {page_number}: {e}")
            await page.close()
            return []


# -------------------------
# Main
# -------------------------
async def scrape_unegui():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )

        first_page = await context.new_page()
        await first_page.goto(START_URL)
        await first_page.wait_for_selector(".advert__section")

        total_pages = await get_total_pages(first_page)
        print("Total pages:", total_pages)

        await first_page.close()

        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        tasks = [
            scrape_page(context, i, semaphore)
            for i in range(1, total_pages + 1)
        ]

        results = await asyncio.gather(*tasks)

        # flatten list
        all_data = [item for sublist in results for item in sublist]

        print(f"Нийт {len(all_data)} зар олдлоо.")

        with open("unegui_data_v1.json", "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(scrape_unegui())