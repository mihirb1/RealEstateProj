import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from openai import OpenAI
import json


AUTH = 'brd-customer-hl_50041442-zone-real_estate_project:a488m31aonc6'
SBR_WS_CDP = f'wss://{AUTH}@brd.superproxy.io:9222'
BASE_URL = "https://zoopla.co.uk"
client = OpenAI(
    api_key = "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")
LOCATION = "London"


def extract_picture(picture_section):
    picture_sources = []
    if not picture_section:
        return picture_sources
    for picture in picture_section.find_all("picture"):
        for source in picture.find_all("source"):
            source_type = source.get("type", "").split("/")[-1]
            pic_url = source.get("srcset", "").split(",")[0].split(" ")[0]
            if source_type == "webp":
                picture_sources.append(pic_url)
    return picture_sources


def extract_property_details(input):
    print("Extracting property details")
    command = """
        You are a data extractor model. Extract the following HTML into ONLY a valid JSON object, with NO explanation or markdown.

        HTML:  
        {input_command} 

        This is the final json structure expected:
        {{
            "price": "",
            "address": "",
            "description": "",
            "bedrooms": "",
            "bathrooms": "",
            "receptions": "",
            "epc_rating": "",
        }}
    """.format(input_command = input)
    response = client.chat.completions.create(
        model = "gpt-4o-mini",
        messages = [
            {
                "role": "user",
                "content": command
            }
        ]
    )
    res = response.choices[0].message.content
    json_data = json.loads(res)

    return json_data


def extract_floor_plan(soup):
    print("Extracting floor plan")

    plan = {}
    floor_plan = soup.find("img", class_ = "_15j4h5e5 _15j4h5e7")
    if floor_plan:
        plan["floor_plan"] = floor_plan.get("src")
    return plan


async def run(pw):
    print('Connecting to Browser API...')
    browser = await pw.chromium.connect_over_cdp(SBR_WS_CDP)
    try:
        page = await browser.new_page()
        print(f'Connected! Navigating to {BASE_URL}')
        await page.goto(BASE_URL)

        # enter location in search bar
        await page.fill('input[name="autosuggest-input"]', LOCATION)
        await page.keyboard.press("Enter")
        print("Waiting for search results...")

        await page.wait_for_selector('div[data-testid="regular-listings"]', timeout = 10000)
        content = await page.inner_html('div[data-testid="regular-listings"]')
        soup = BeautifulSoup(content, "html.parser")

        for idx, div in enumerate(soup.find_all("div", class_ = "dkr2t86")):
            data = {}
            link = div.find('a')['href']
            data["address"] = div.find('address').text.strip()
            data["link"] = BASE_URL + link

            # Go to the listing page
            await page.goto(data['link'])
            await page.wait_for_selector('div._1olqsf91', timeout = 10000)

            listing_html = await page.inner_html('div._1olqsf91')
            listing_soup = BeautifulSoup(listing_html, "html.parser")

            # Now we are on the correct page to find the <h1>
            title_tag = listing_soup.find("h1", class_ = "_194zg6t8 _1olqsf97")
            title = title_tag.find(string = True, recursive = False).strip() if title_tag else "N/A"
            data["title"] = title

            print("Navigating to the listing page", link)
            await page.goto(data['link'])
            await page.wait_for_selector('div._1olqsf91', timeout = 10000)

            content = await page.inner_html('div._1olqsf91')
            soup = BeautifulSoup(content, "html.parser")
            picture_section = soup.find("ol", class_ = "_15j4h5e1")
            pictures = extract_picture(picture_section)
            data['pictures'] = pictures

            property_html = str(soup)
            property_details = extract_property_details(property_html)
            floor_plan = extract_floor_plan(soup)

            data.update(floor_plan)
            data.update(property_details)
            print(data)
            break

        print('Navigated! Scraping page content...')
    finally:
        await browser.close()


async def main():
    async with async_playwright() as playwright:
        await run(playwright)


if __name__ == '__main__':
    asyncio.run(main())
