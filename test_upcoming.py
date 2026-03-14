from bs4 import BeautifulSoup
import re
import json
from datetime import datetime

soup = BeautifulSoup(open('debug_index.txt', 'r', encoding='utf-8'), 'html.parser')
upcoming = []
now = datetime.now()

table_divs = soup.find_all("div", class_="table1")
found = 0
for div in table_divs:
    # 開催場へのリンクを探す
    venue_links = div.find_all("a", href=re.compile(r"jcd=\d+"))
    if not venue_links: continue
    
    # 開催ごとのブロック
    for v_link in venue_links:
        href = v_link.get("href", "")
        jcd_match = re.search(r"jcd=(\d+)", href)
        if not jcd_match: continue
        
        jcd = jcd_match.group(1)
        venue_name = v_link.get_text(strip=True)
        
        # 同じ親(trやtbody)のレベルにある td を探す方法だとずれるため、
        # div全体からこの場のレースリンク（rno=X&jcd=Y）を探して時間を推測する
        # indexページでは、各レースのaタグの中に時間がかかれている場合と、親tdに書かれている場合がある。
        
        # この jcd に紐づくレースリンクをすべて取得
        race_links = div.find_all("a", href=re.compile(r"rno=\d+&jcd=" + jcd))
        processed_rno = set()
        for r_link in race_links:
            r_href = r_link.get("href", "")
            rno_match = re.search(r"rno=(\d+)", r_href)
            if not rno_match: continue
            
            race_no = int(rno_match.group(1))
            if race_no in processed_rno: continue
            processed_rno.add(race_no)
            
            # リンクの親（だいたいtdまたはdiv）からテキスト抽出
            parent = r_link.find_parent(["td", "li"])
            text = parent.get_text(strip=True) if parent else r_link.get_text(strip=True)
            
            # 時間（10:57など）を探す
            m = re.search(r'(\d{1,2}:\d{2})', text)
            if m:
                time_str = m.group(1)
                
                try:
                    today_str = now.strftime("%Y-%m-%d")
                    dt_str = f"{today_str} {time_str}"
                    deadline_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                    diff_minutes = (deadline_dt - now).total_seconds() / 60.0
                    
                    upcoming.append({
                        "jcd": jcd,
                        "venue": venue_name,
                        "race_no": race_no,
                        "deadline": time_str,
                        "minutes_left": int(diff_minutes)
                    })
                except:
                    pass

upcoming.sort(key=lambda x: x["minutes_left"])
print(f"Total valid races found: {len(upcoming)}")
for u in upcoming[:10]:
    print(u)
