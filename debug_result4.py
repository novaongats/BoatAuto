import requests
from bs4 import BeautifulSoup

# 別URLパターンを試す
urls = [
    "https://www.boatrace.jp/owpc/pc/race/raceresult?rno=3&jcd=23&hd=20260319",
    "https://www.boatrace.jp/owpc/pc/race/result?rno=3&jcd=23&hd=20260319",
    "https://www.boatrace.jp/owpc/pc/race/raceresult?rno=1&jcd=23&hd=20260319",
]

for url in urls:
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        divs = soup.find_all("div", class_="table1")
        text = soup.get_text(strip=True)
        has_rank = any(c in text for c in ["１着", "1着", "着順", "確定"])
        print(f"URL={url}")
        print(f"  divs={len(divs)}, page_size={len(text)}, has_rank={has_rank}")
        if len(divs) >= 2:
            t2 = divs[1].get_text(separator="|", strip=True)[:200]
            print(f"  div[1]: {t2}")
    except Exception as e:
        print(f"Error {url}: {e}")
