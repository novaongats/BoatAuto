import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz

jst_now = datetime.now(pytz.timezone('Asia/Tokyo'))
date_str = jst_now.strftime("%Y%m%d")

# 唐津4Rで試す (直前に終わったレースのいずれか)
jcd = "23"
race_no = 4
url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?rno={race_no}&jcd={jcd}&hd={date_str}"
print(f"URL: {url}")

resp = requests.get(url, timeout=15)
resp.encoding = "utf-8"
soup = BeautifulSoup(resp.text, "html.parser")

# div.table1 いくつある？
divs = soup.find_all("div", class_="table1")
print(f"div.table1 count: {len(divs)}")

for i, d in enumerate(divs[:5]):
    text = d.get_text(separator="|", strip=True)[:200]
    print(f"  div[{i}]: {text}")
    
# tbodyを全部確認
print("\n--- All tbodys ---")
all_tbodies = soup.find_all("tbody")
for i, tb in enumerate(all_tbodies[:6]):
    text = tb.get_text(separator="|", strip=True)[:150]
    print(f"  tbody[{i}]: {text}")
