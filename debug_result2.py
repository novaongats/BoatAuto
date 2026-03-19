import requests
from bs4 import BeautifulSoup

# 以前に終わったレースをいくつか試す
tests = [
    ("23", 1, "20260319"),
    ("23", 2, "20260319"),
    ("23", 3, "20260319"),
    ("11", 1, "20260319"),
    ("11", 2, "20260319"),
    ("11", 3, "20260319"),
]

for jcd, rno, hd in tests:
    url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?rno={rno}&jcd={jcd}&hd={hd}"
    resp = requests.get(url, timeout=15)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    
    divs = soup.find_all("div", class_="table1")
    text = soup.get_text(separator=" ", strip=True)
    
    # 着順らしきキーワードを検索
    has_result = any(kw in text for kw in ["着順", "3連単", "払戻", "1着", "確定"])
    
    print(f"jcd={jcd} rno={rno}: divs={len(divs)}, has_result={has_result}, page_len={len(text)}")
    if has_result:
        # テーブルの最初の内容を見る
        for d in divs[:3]:
            t = d.get_text(separator="|", strip=True)[:200]
            print(f"  -> {t}")
        break
