import requests
from bs4 import BeautifulSoup
import re
from typing import Dict, List, Optional
from datetime import datetime
import pytz

# 競艇場コード → 場名 マッピング
VENUE_NAMES = {
    "01": "桐生", "02": "戸田", "03": "江戸川", "04": "平和島",
    "05": "多摩川", "06": "浜名湖", "07": "蒲郡", "08": "常滑",
    "09": "津", "10": "三国", "11": "びわこ", "12": "住之江",
    "13": "尼崎", "14": "鳴門", "15": "丸亀", "16": "児島",
    "17": "宮島", "18": "徳山", "19": "下関", "20": "若松",
    "21": "芦屋", "22": "福岡", "23": "唐津", "24": "大村",
}


class KyoteiScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.base_url = "https://www.boatrace.jp/owpc/pc/race"

    def _get_jst_now(self) -> datetime:
        """常に日本時間（JST）の現在日時を返す"""
        return datetime.now(pytz.timezone('Asia/Tokyo'))

    def get_race_list(self, date_str: str = None) -> List[Dict]:
        """
        指定した日付（YYYYMMDD）の開催レース場一覧を取得。
        """
        if not date_str:
            date_str = self._get_jst_now().strftime("%Y%m%d")

        url = f"{self.base_url}/index?hd={date_str}"
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            venues = []
            # raceindex リンクから開催場を抽出
            links = soup.find_all("a", href=re.compile(r"raceindex\?jcd=\d+"))
            seen = set()
            for link in links:
                href = link.get("href", "")
                m = re.search(r"jcd=(\d+)", href)
                if m:
                    jcd = m.group(1)
                    if jcd not in seen:
                        seen.add(jcd)
                        title = link.get_text(strip=True)
                        venues.append({
                            "jcd": jcd,
                            "name": VENUE_NAMES.get(jcd, f"場{jcd}"),
                            "title": title,
                        })
            return venues
        except Exception as e:
            print(f"Error fetching race list: {e}")
            return []

    def get_upcoming_races(self, max_minutes: int = 30) -> List[Dict]:
        """
        全開催場から、直近（デフォルト30分以内）に締切を迎えるレースのリストを取得する。
        """
        date_str = self._get_jst_now().strftime("%Y%m%d")
        url = f"{self.base_url}/index?hd={date_str}"
        
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            
            upcoming = []
            now = self._get_jst_now()
            
            table_divs = soup.find_all("div", class_="table1")
            for div in table_divs:
                rows = div.find_all("tbody")
                for row in rows:
                    jcd = "00"
                    venue_name = "不明"
                    
                    venue_link = row.find("a", href=re.compile(r"jcd=\d+"))
                    if venue_link:
                        venue_href = venue_link.get("href", "")
                        jcd_match = re.search(r"jcd=(\d+)", venue_href)
                        if jcd_match: jcd = jcd_match.group(1)
                        venue_name = venue_link.get_text(strip=True)
                        
                    img = row.find("img", alt=True)
                    if img and venue_name == "不明":
                        venue_name = img.get("alt")
                        
                    if jcd == "00": continue

                    tds = row.find_all("td", class_="is-p10-0")
                    if not tds:
                        tds = row.find_all("td")

                    race_no = 1
                    for td in tds:
                        time_text = td.get_text(strip=True)
                        m = re.search(r'(\d{1,2}:\d{2})', time_text)
                        if m:
                            time_str = m.group(1)
                            try:
                                today_str = now.strftime("%Y-%m-%d")
                                dt_str = f"{today_str} {time_str}"
                                deadline_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                                deadline_dt = pytz.timezone('Asia/Tokyo').localize(deadline_dt)
                                diff_minutes = (deadline_dt - now).total_seconds() / 60.0
                                
                                if -5 <= diff_minutes <= max_minutes:
                                    upcoming.append({
                                        "jcd": jcd,
                                        "venue": venue_name,
                                        "race_no": race_no,
                                        "deadline": time_str,
                                        "minutes_left": int(diff_minutes)
                                    })
                            except:
                                pass
                            race_no += 1

            upcoming.sort(key=lambda x: x["minutes_left"])
            return upcoming
            
        except Exception as e:
            print(f"Error fetching upcoming races: {e}")
            return []

    def get_race_program(self, jcd: str, race_no: int, date_str: str = None) -> Dict:
        """
        指定したレース場・レース番号の出走表データを取得。
        標準のrequests + BeautifulSoupで静的HTMLから解析する。
        """
        if not date_str:
            date_str = self._get_jst_now().strftime("%Y%m%d")

        url = f"{self.base_url}/racelist?rno={race_no}&jcd={jcd}&hd={date_str}"
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            entries = []
            # 選手リンク（racersearch/profile）から名前を取得
            racer_links = soup.find_all("a", href=re.compile(r"racersearch/profile"))
            seen_tobans = []
            for link in racer_links:
                name_text = link.get_text(strip=True)
                if not name_text:
                    continue  # テキストなしのリンク（画像リンク等）はスキップ
                href = link.get("href", "")
                toban_match = re.search(r"toban=(\d+)", href)
                toban = toban_match.group(1) if toban_match else ""
                if toban in seen_tobans:
                    continue  # 重複スキップ
                seen_tobans.append(toban)

                entry = {
                    "waku": len(seen_tobans),
                    "name": re.sub(r"\s+", " ", name_text),
                    "toban": toban,
                }
                entries.append(entry)

            # 締切時刻の取得
            deadline = ""
            schedule_tables = soup.find_all("table", class_="table1")
            for st in schedule_tables:
                trs = st.find_all("tr")
                if len(trs) >= 2:
                    headers = trs[0].find_all(["th", "td"])
                    values = trs[1].find_all(["th", "td"])
                    for j, h in enumerate(headers):
                        h_text = h.get_text(strip=True)
                        if h_text == f"{race_no}R" and j < len(values):
                            time_text = values[j].get_text(strip=True)
                            time_match = re.search(r"(\d{1,2}:\d{2})", time_text)
                            if time_match:
                                deadline = time_match.group(1)
                                break
                    if deadline:
                        break
            if not deadline:
                time_matches = re.findall(r"(\d{1,2}:\d{2})", soup.get_text())
                if time_matches:
                    deadline = time_matches[0]

            # レースタイトルの取得
            race_title = ""
            title_tag = soup.find("div", class_="heading2_titleName")
            if not title_tag:
                title_tag = soup.find("h2", class_="heading2_titleName")
            if title_tag:
                race_title = title_tag.get_text(strip=True)

            return {
                "jcd": jcd,
                "venue": VENUE_NAMES.get(jcd, f"場{jcd}"),
                "race_no": race_no,
                "date": date_str,
                "title": race_title,
                "deadline": deadline,
                "entries": entries,
            }
        except Exception as e:
            error_msg = f"Error fetching race program for jcd={jcd} rno={race_no}: {e}\n"
            print(error_msg)
            try:
                with open("debug_log.txt", "a", encoding="utf-8") as f:
                    f.write(error_msg)
            except:
                pass
            return {}

    def get_race_result(self, jcd: str, race_no: int, date_str: str = None) -> Dict:
        """
        レース結果を取得
        """
        if not date_str:
            date_str = self._get_jst_now().strftime("%Y%m%d")

        url = f"{self.base_url}/raceresult?rno={race_no}&jcd={jcd}&hd={date_str}"
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            result = {
                "jcd": jcd,
                "venue": VENUE_NAMES.get(jcd, f"場{jcd}"),
                "race_no": race_no,
                "date": date_str,
                "order": [],
                "payouts": {},
            }

            # 着順テーブル
            result_table = soup.find("div", class_="table1")
            if result_table:
                rows = result_table.find_all("tbody")
                for tbody in rows:
                    tds = tbody.find_all("td")
                    if len(tds) >= 2:
                        waku = tds[0].get_text(strip=True)
                        result["order"].append(waku)

            # 払戻金テーブル
            payout_table = soup.find("div", class_="table1", id=re.compile(r"payout"))
            if not payout_table:
                # 別の方法で払戻金テーブルを探す
                all_tables = soup.find_all("div", class_="table1")
                for t in all_tables:
                    if "3連単" in t.get_text() or "払戻金" in t.get_text():
                        payout_table = t
                        break

            if payout_table:
                rows = payout_table.find_all("tr")
                for row in rows:
                    header = row.find("th")
                    value = row.find("td")
                    if header and value:
                        bet_type = header.get_text(strip=True)
                        payout_text = value.get_text(strip=True)
                        # 数字のみ抽出
                        payout_num = re.sub(r"[^\d]", "", payout_text)
                        if payout_num:
                            result["payouts"][bet_type] = int(payout_num)

            return result
        except Exception as e:
            print(f"Error fetching race result: {e}")
            return {}


if __name__ == "__main__":
    import json
    scraper = KyoteiScraper()

    print("=== 本日の開催 ===")
    venues = scraper.get_race_list()
    print(json.dumps(venues, ensure_ascii=False, indent=2))

    if venues:
        jcd = venues[0]["jcd"]
        print(f"\n=== {venues[0]['name']} 1R 出走表 ===")
        program = scraper.get_race_program(jcd=jcd, race_no=1)
        print(json.dumps(program, ensure_ascii=False, indent=2))
