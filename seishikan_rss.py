import requests
from bs4 import BeautifulSoup, NavigableString, Tag
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
import hashlib
import re

URL = "https://www.fukuyamaseishikan-h.hiroshima-c.ed.jp/"
OUTPUT = Path(__file__).parent / "seishikan.xml"

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

response = requests.get(
    URL,
    headers=headers,
    timeout=30
)

response.raise_for_status()
response.encoding = "utf-8"

soup = BeautifulSoup(response.text, "html.parser")

jst = timezone(timedelta(hours=9))

date_pattern = re.compile(
    r"令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日"
)

new_items = []
seen = set()

for li in soup.find_all("li"):

    # li直下の内容だけを取得する
    # 入れ子になった次の記事は含めない
    parts = []
    article_url = ""

    for child in li.children:

        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                parts.append(text)

        elif isinstance(child, Tag):

            # 子のliは別記事なので無視
            if child.name == "li":
                continue

            if child.name == "a":
                link_text = child.get_text(" ", strip=True)

                if link_text:
                    parts.append(link_text)

                if not article_url and child.get("href"):
                    article_url = urljoin(
                        URL,
                        child["href"]
                    )

            else:
                text = child.get_text(" ", strip=True)

                if text:
                    parts.append(text)

    full_text = " ".join(parts)
    full_text = re.sub(r"\s+", " ", full_text).strip()

    match = date_pattern.search(full_text)

    if not match:
        continue

    reiwa, month, day = map(int, match.groups())

    # 令和 → 西暦
    year = reiwa + 2018

    # 日付をタイトルから除去
    title = date_pattern.sub("", full_text, count=1).strip()

    if not title:
        continue

    # リンクがない項目は除外
    if not article_url:
        continue

    dt = datetime(
        year,
        month,
        day,
        0,
        0,
        tzinfo=jst
    )

    pub_date = format_datetime(dt)

    # 同じURLを何度も更新するサイトなので
    # 日付＋タイトル＋URLを固有IDにする
    guid_source = (
        f"{year}-{month:02d}-{day:02d}|"
        f"{title}|{article_url}"
    )

    guid = hashlib.sha256(
        guid_source.encode("utf-8")
    ).hexdigest()

    if guid in seen:
        continue

    seen.add(guid)

    new_items.append({
        "title": title,
        "link": article_url,
        "description": "広島県立福山誠之館高等学校 What's New",
        "date": pub_date,
        "guid": guid
    })

# 日付順に並べる
new_items.sort(
    key=lambda x: datetime.strptime(
        x["date"],
        "%a, %d %b %Y %H:%M:%S %z"
    ),
    reverse=True
)

# 以前のRSSを読み込む
old_items = []

if OUTPUT.exists():
    try:
        old_tree = ET.parse(OUTPUT)
        old_root = old_tree.getroot()

        for item in old_root.findall("./channel/item"):
            old_items.append({
                "title": item.findtext("title", ""),
                "link": item.findtext("link", ""),
                "description": item.findtext("description", ""),
                "date": item.findtext("pubDate", ""),
                "guid": item.findtext("guid", "")
            })

    except Exception:
        old_items = []

# 新着＋過去記事
all_items = []
seen_guids = set()

for item in new_items + old_items:

    if item["guid"] in seen_guids:
        continue

    seen_guids.add(item["guid"])
    all_items.append(item)

all_items = all_items[:300]

# RSS作成
rss = ET.Element("rss", version="2.0")
channel = ET.SubElement(rss, "channel")

ET.SubElement(
    channel,
    "title"
).text = "広島県立福山誠之館高等学校 What's New"

ET.SubElement(
    channel,
    "link"
).text = URL

ET.SubElement(
    channel,
    "description"
).text = "広島県立福山誠之館高等学校の新着情報"

ET.SubElement(
    channel,
    "language"
).text = "ja"

for item in all_items:

    element = ET.SubElement(channel, "item")

    ET.SubElement(
        element,
        "title"
    ).text = item["title"]

    ET.SubElement(
        element,
        "link"
    ).text = item["link"]

    ET.SubElement(
        element,
        "description"
    ).text = item["description"]

    ET.SubElement(
        element,
        "pubDate"
    ).text = item["date"]

    guid_element = ET.SubElement(
        element,
        "guid"
    )

    guid_element.set(
        "isPermaLink",
        "false"
    )

    guid_element.text = item["guid"]

tree = ET.ElementTree(rss)
ET.indent(tree, space="  ")

tree.write(
    OUTPUT,
    encoding="utf-8",
    xml_declaration=True
)

print("RSS作成成功")
print("今回取得:", len(new_items), "件")
print("RSS保存件数:", len(all_items), "件")
print("保存先:", OUTPUT)

print()
print("最新15件:")

for item in new_items[:15]:
    print(
        item["date"],
        item["title"]
    )