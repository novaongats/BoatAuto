import requests
from bs4 import BeautifulSoup

# 直近終わったレースを探す
for jcd in ["23", "11", "13", "21"]:
    for rno in [3, 4, 5]:
        url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?rno={rno}&jcd={jcd}&hd=20260319"
        resp = requests.get(url, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        divs = soup.find_all("div", class_="table1")
        text = soup.get_text(strip=True)
        has_order = "１" in text and "枠" in text
        print(f"jcd={jcd} rno={rno}: divs={len(divs)}, has_order={has_order}")
        
        if len(divs) >= 2:
            # 着順tbody取得テスト
            tbody = divs[1].find("tbody")
            if tbody:
                tds = tbody.find_all("td")
                print(f"  -> first tds: {[td.get_text(strip=True) for td in tds[:6]]}")
