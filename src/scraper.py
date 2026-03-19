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
                    # 会場コード（jcd）の取得
                    jcd = "00"
                    venue_name = "不明"
                    venue_link = row.find("a", href=re.compile(r"jcd=\d+"))
                    if venue_link:
                        href = venue_link.get("href", "")
                        jcd_match = re.search(r"jcd=(\d+)", href)
                        if jcd_match:
                            jcd = jcd_match.group(1)
                    # リンクテキストは大会名が入るので、VENUE_NAMESから正式な会場名を取得
                    venue_name = VENUE_NAMES.get(jcd, f"場{jcd}")

                    if jcd == "00":
                        continue

                    tds = row.find_all("td")
                    race_no = None
                    deadline_time = None

                    for td in tds:
                        text = td.get_text(strip=True)
                        # "3R" のようなセルからレース番号を取得
                        r_match = re.match(r'^(\d+)R$', text)
                        if r_match:
                            race_no = int(r_match.group(1))
                        # "11:55" のような時刻セルから締切時刻を取得
                        t_match = re.search(r'(\d{1,2}:\d{2})', text)
                        if t_match and race_no is not None and deadline_time is None:
                            deadline_time = t_match.group(1)

                    if race_no is None or deadline_time is None:
                        continue

                    try:
                        today_str = now.strftime("%Y-%m-%d")
                        deadline_dt = datetime.strptime(f"{today_str} {deadline_time}", "%Y-%m-%d %H:%M")
                        deadline_dt = pytz.timezone("Asia/Tokyo").localize(deadline_dt)
                        diff_minutes = (deadline_dt - now).total_seconds() / 60.0

                        if -5 <= diff_minutes <= max_minutes:
                            upcoming.append({
                                "jcd": jcd,
                                "venue": venue_name,
                                "race_no": race_no,
                                "deadline": deadline_time,
                                "minutes_left": int(diff_minutes),
                            })
                    except Exception:
                        pass

            upcoming.sort(key=lambda x: x["minutes_left"])
            return upcoming

        except Exception as e:
            print(f"Error fetching upcoming races: {e}")
            return []


    def get_race_program(self, jcd: str, race_no: int, date_str: str = None) -> Dict:
        """
        指定したレース場・レース番号の出走表データを取得。
        選手・モーター・ボート統計も含む拡張版。
        """
        if not date_str:
            date_str = self._get_jst_now().strftime("%Y%m%d")

        url = f"{self.base_url}/racelist?rno={race_no}&jcd={jcd}&hd={date_str}"
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")

            # --- 締切時刻の取得 ---
            deadline = ""
            schedule_divs = soup.find_all("div", class_="table1")
            if schedule_divs:
                trs = schedule_divs[0].find_all("tr")
                for tr in trs:
                    ths = tr.find_all(["th", "td"])
                    for j, th in enumerate(ths):
                        if th.get_text(strip=True) == f"{race_no}R" and j + 1 < len(ths):
                            t = re.search(r"(\d{1,2}:\d{2})", ths[j + 1].get_text())
                            if t:
                                deadline = t.group(1)
                if not deadline:
                    all_times = re.findall(r"\d{1,2}:\d{2}", schedule_divs[0].get_text())
                    if all_times:
                        deadline = all_times[0]

            # --- レースタイトルの取得 ---
            race_title = ""
            for cls in ["heading2_titleName", "heading1_title"]:
                tag = soup.find(["div", "h2", "span"], class_=cls)
                if tag:
                    race_title = tag.get_text(strip=True)
                    break

            # --- 出走選手データの取得 ---
            entries = []
            entry_div = schedule_divs[1] if len(schedule_divs) > 1 else None
            if not entry_div:
                return {}

            tbody_list = entry_div.find_all("tbody")

            def _safe_float(s):
                try:
                    return float(s)
                except (ValueError, TypeError):
                    return None

            def _safe_int(s):
                try:
                    return int(s)
                except (ValueError, TypeError):
                    return None

            for waku_idx, tbody in enumerate(tbody_list, start=1):
                # 選手名 + 登番: プロファイルリンクatagが2つある（1つは画像用で空, もう1つがテキスト）
                name = ""
                toban = ""
                for a in tbody.find_all("a", href=re.compile(r"racersearch/profile")):
                    t = a.get_text(strip=True)
                    if t:  # テキストがあるほうが選手名
                        name = re.sub(r"\s+", " ", t)
                        m = re.search(r"toban=(\d+)", a.get("href", ""))
                        if m:
                            toban = m.group(1)
                        break
                # 名前が取れなかった場合はtobanだけでも取る
                if not toban:
                    first_a = tbody.find("a", href=re.compile(r"racersearch/profile"))
                    if first_a:
                        m = re.search(r"toban=(\d+)", first_a.get("href", ""))
                        if m:
                            toban = m.group(1)

                tds = tbody.find_all("td")

                def td_text(i):
                    return tds[i].get_text(strip=True) if i < len(tds) else ""

                # 級別 (td[2] の / より前)
                toban_grade = td_text(2)
                grade = ""
                g_match = re.search(r"(A1|A2|B1|B2)", toban_grade)
                if g_match:
                    grade = g_match.group(1)

                # F数・L数・平均ST (td[3]: "F0L00.12" のような文字列)
                fl_st_raw = td_text(3)
                f_match = re.search(r"F(\d+)", fl_st_raw)
                l_match = re.search(r"L(\d+)", fl_st_raw)
                st_match = re.search(r"(\d+\.\d+)$", fl_st_raw)
                f_count = _safe_int(f_match.group(1)) if f_match else 0
                l_count = _safe_int(l_match.group(1)) if l_match else 0
                avg_st = _safe_float(st_match.group(1)) if st_match else None

                # 全国・当地・モーター・ボートのデータを <br/> で区切られた文字列から切り出す
                def parse_td_values(td_elem):
                    """tdの中のテキストをbrタグで分割して数値リストにする"""
                    parts = [s.strip() for s in td_elem.stripped_strings]
                    nums = []
                    for p in parts:
                        m = re.match(r'^[\d.]+$', p)
                        if m:
                            nums.append(p)
                    while len(nums) < 3:
                        nums.append(None)
                    return nums[:3]

                n_win, n_2ren, n_3ren = parse_td_values(tds[4]) if len(tds) > 4 else [None, None, None]
                l_win, l_2ren, l_3ren = parse_td_values(tds[5]) if len(tds) > 5 else [None, None, None]
                motor_vals = parse_td_values(tds[6]) if len(tds) > 6 else [None, None, None]
                boat_vals = parse_td_values(tds[7]) if len(tds) > 7 else [None, None, None]

                motor_no = _safe_int(motor_vals[0])
                motor_2ren = _safe_float(motor_vals[1])
                motor_3ren = _safe_float(motor_vals[2])

                boat_no = _safe_int(boat_vals[0])
                boat_2ren = _safe_float(boat_vals[1])
                boat_3ren = _safe_float(boat_vals[2])

                entries.append({
                    "waku": waku_idx,
                    "name": name,
                    "toban": toban,
                    "grade": grade,
                    "f_count": f_count,
                    "l_count": l_count,
                    "avg_st": avg_st,
                    "national_win_rate": _safe_float(n_win),
                    "national_2ren": _safe_float(n_2ren),
                    "national_3ren": _safe_float(n_3ren),
                    "local_win_rate": _safe_float(l_win),
                    "local_2ren": _safe_float(l_2ren),
                    "local_3ren": _safe_float(l_3ren),
                    "motor_no": motor_no,
                    "motor_2ren": motor_2ren,
                    "motor_3ren": motor_3ren,
                    "boat_no": boat_no,
                    "boat_2ren": boat_2ren,
                    "boat_3ren": boat_3ren,
                })

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
            return {}


    def get_race_result(self, jcd: str, race_no: int, date_str: str = None) -> Dict:
        """
        レース結果を取得。全 div.table1 から着順テーブルを自動検索する。
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

            tables = soup.find_all("div", class_="table1")
            rank_valid = {"１", "２", "３", "４", "５", "６", "1", "2", "3", "4", "5", "6"}

            # --- 着順の取得: 全 div.table1 から「着」と「枠」を含むものを探す ---
            for t in tables:
                t_text = t.get_text()
                if "着" not in t_text or "枠" not in t_text:
                    continue
                for tbody in t.find_all("tbody"):
                    for tr in tbody.find_all("tr"):
                        tds = tr.find_all("td")
                        if len(tds) < 2:
                            continue
                        rank = tds[0].get_text(strip=True)
                        waku = tds[1].get_text(strip=True)
                        if rank in rank_valid and waku.isdigit():
                            result["order"].append(waku)
                if result["order"]:
                    break

            # --- 払戻金の取得: 全 div.table1 から 3連単 または 払戻 を含むものを探す ---
            for t in tables:
                t_text = t.get_text()
                if "3連単" not in t_text and "払戻" not in t_text:
                    continue
                for tbody in t.find_all("tbody"):
                    for tr in tbody.find_all("tr"):
                        tds = tr.find_all("td")
                        if len(tds) >= 3:
                            bet_type = tds[0].get_text(strip=True)
                            payout_str = tds[2].get_text(strip=True).replace("¥", "").replace(",", "").replace("円", "")
                            if bet_type and re.match(r"^\d+$", payout_str):
                                result["payouts"][bet_type] = int(payout_str)
                        if len(tds) >= 6:
                            bet_type2 = tds[3].get_text(strip=True)
                            payout_str2 = tds[5].get_text(strip=True).replace("¥", "").replace(",", "").replace("円", "")
                            if bet_type2 and re.match(r"^\d+$", payout_str2):
                                result["payouts"][bet_type2] = int(payout_str2)

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
