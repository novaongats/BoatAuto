import json
from datetime import datetime
from playwright.sync_api import sync_playwright

def get_upcoming_js(max_minutes=30):
    upcoming = []
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    url = f"https://www.boatrace.jp/owpc/pc/race/index?hd={date_str}"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # JSでデータをぶっこ抜く
        data = page.evaluate("""() => {
            const results = [];
            const tbodies = document.querySelectorAll('.table1 tbody');
            tbodies.forEach(tbody => {
                const jcdTag = tbody.querySelector('a[href*="jcd="]');
                if (!jcdTag) return;
                
                const href = jcdTag.getAttribute('href');
                const jcdMatch = href.match(/jcd=(\d+)/);
                if (!jcdMatch) return;
                const jcd = jcdMatch[1];
                
                let venue = "不明";
                const img = jcdTag.querySelector('img');
                if (img) venue = img.getAttribute('alt');
                else venue = jcdTag.innerText.trim();
                
                // 1R〜12Rのすべての aタグ リンクを取得
                const raceLinks = tbody.querySelectorAll('a[href*="rno="]');
                const seenRaces = new Set();
                
                raceLinks.forEach(link => {
                    const r_href = link.getAttribute('href');
                    if (!r_href.includes('jcd=' + jcd)) return;
                    
                    const rnoMatch = r_href.match(/rno=(\d+)/);
                    if (!rnoMatch) return;
                    
                    const raceNo = parseInt(rnoMatch[1]);
                    if (seenRaces.has(raceNo)) return;
                    seenRaces.add(raceNo);
                    
                    // aタグの祖先tdにあるテキストを取得（時刻が書いてある）
                    const td = link.closest('td') || link.parentElement;
                    let timeText = td ? td.innerText : link.innerText;
                    
                    results.push({
                        jcd: jcd,
                        venue: venue,
                        race_no: raceNo,
                        time_text: timeText
                    });
                });
            });
            return results;
        }""")
        
        browser.close()
        
    # JSから返ってきたデータ（リスト）を整形
    import re
    for d in data:
        m = re.search(r'(\d{1,2}:\d{2})', d.get("time_text", ""))
        if m:
            time_str = m.group(1)
            try:
                today_str = now.strftime("%Y-%m-%d")
                dt_str = f"{today_str} {time_str}"
                deadline_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                diff_minutes = (deadline_dt - now).total_seconds() / 60.0
                
                if diff_minutes >= -5: # -5分〜 のものを含める（すでに終わったものを過剰に除外しない）
                    upcoming.append({
                        "jcd": d["jcd"],
                        "venue": d["venue"],
                        "race_no": d["race_no"],
                        "deadline": time_str,
                        "minutes_left": int(diff_minutes)
                    })
            except:
                pass
                
    upcoming.sort(key=lambda x: x["minutes_left"])
    return upcoming

if __name__ == "__main__":
    res = get_upcoming_js(120)
    print(f"Total: {len(res)}")
    for r in res[:20]:
        print(r)
