"""
レース結果の的中判定とドヤ投稿生成モジュール
"""
import re
import json
import os
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv


class ResultChecker:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None

        # ペルソナ読み込み
        personas_file = os.path.join(os.path.dirname(__file__), "personas.json")
        if os.path.exists(personas_file):
            with open(personas_file, 'r', encoding='utf-8') as f:
                self.personas = json.load(f)
        else:
            self.personas = {}

    def parse_bets_from_article(self, article_text: str) -> Dict[str, List[str]]:
        """
        生成された予想記事から買い目を抽出する。
        戻り値: {"honsen": ["3-1-2", "3-2-1", ...], "atsuo": [...], "osae": [...]}
        """
        result = {"honsen": [], "atsuo": [], "osae": []}
        current_section = None

        for line in article_text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # セクション判定
            if "本線" in line:
                current_section = "honsen"
                # 同一行に買い目がある場合
                bets = re.findall(r"(\d-\d(?:-\d)?)", line)
                if bets:
                    result["honsen"].extend(bets)
                continue
            elif "熱男スペシャル" in line or "熱男" in line:
                current_section = "atsuo"
                bets = re.findall(r"(\d-\d(?:-\d)?)", line)
                if bets:
                    result["atsuo"].extend(bets)
                continue
            elif "抑え" in line:
                current_section = "osae"
                bets = re.findall(r"(\d-\d(?:-\d)?)", line)
                if bets:
                    result["osae"].extend(bets)
                continue

            # 買い目の行（例: 3-1-2, 5-14-146, 5-1=4）
            if current_section:
                # "=" を "-" に正規化 (2連単表記)
                normalized = line.replace("=", "-")
                bets = re.findall(r"(\d-\d+(?:-\d+)?)", normalized)
                if bets:
                    result[current_section].extend(bets)

        return result

    def check_hit(self, bets: Dict[str, List[str]], race_result: Dict) -> Dict:
        """
        買い目とレース結果を照合して的中判定する。
        race_result: scraper の get_race_result の戻り値全体
        """
        hit_result = {
            "is_hit": False,
            "hit_section": None,
            "hit_bet": None,
            "result_str": "",
            "payout": 0,
        }

        race_result_order = race_result.get("order", [])
        payouts = race_result.get("payouts", {})

        if len(race_result_order) < 3:
            return hit_result

        result_3tan = f"{race_result_order[0]}-{race_result_order[1]}-{race_result_order[2]}"
        result_2tan = f"{race_result_order[0]}-{race_result_order[1]}"
        hit_result["result_str"] = result_3tan

        for section in ["atsuo", "honsen", "osae"]:
            for bet in bets.get(section, []):
                if bet == result_3tan:
                    hit_result["is_hit"] = True
                    hit_result["hit_section"] = section
                    hit_result["hit_bet"] = bet
                    hit_result["payout"] = payouts.get("3連単", 0)
                    return hit_result
                parts = bet.split("-")
                if len(parts) == 2 and bet == result_2tan:
                    hit_result["is_hit"] = True
                    hit_result["hit_section"] = section
                    hit_result["hit_bet"] = bet
                    hit_result["payout"] = payouts.get("2連単", 0)
                    return hit_result
                if len(parts) == 3:
                    first_digits = list(parts[0])
                    second_digits = list(parts[1])
                    third_digits = list(parts[2])
                    if (race_result_order[0] in first_digits and
                            race_result_order[1] in second_digits and
                            race_result_order[2] in third_digits):
                        hit_result["is_hit"] = True
                        hit_result["hit_section"] = section
                        hit_result["hit_bet"] = bet
                        hit_result["payout"] = payouts.get("3連単", 0)
                        return hit_result

        return hit_result

    def generate_doya_post(self, hit_info: Dict, race_info: Dict, persona_name: str = "default") -> Dict[str, str]:
        # 中情報からドヤ投稿テキストを生成する。
        if not self.client:
            return {"note": "APIキー未設定", "x": "APIキー未設定", "line": "APIキー未設定"}

        section_names = {
            "honsen": "本線",
            "atsuo": "熱男スペシャル💎",
            "osae": "抑え",
        }
        section_name = section_names.get(hit_info.get("hit_section", ""), "予想")

        system_prompt = self.personas.get(persona_name, {}).get("system_prompt", "あなたは競艇予想家です。")
        system_prompt += "\n\n的中したことを報告する「ドヤ投稿」を作成してください。興奮と喜びを短く熱く表現してください。"

        venue = race_info.get("venue", "")
        race_no = race_info.get("race_no", "")
        result_str = hit_info.get("result_str", "").replace("-", "") # 3-1-2 -> 312
        hit_bet = hit_info.get("hit_bet", "")
        payout = hit_info.get("payout", 0)
        payout_str = f"{payout:,}" # カンマ区切り

        user_prompt = f"""
以下の的中情報をもとに、各プラットフォーム用のドヤ投稿（コピペ用テキスト）を作成してください。

【的中情報】
- レース場と番号: {venue}{race_no}R
- 結果(的中目): {result_str}
- 払戻金: {payout_str}円
- 的中した買い目区分: {section_name}

【厳密な出力フォーマット・ルール】
必ず以下の「例」と全く同じフォーマット（記号の配置や順番）でテキストの冒頭を作ってください。
例：「徳山5R🎯324🎯4,080円㊗️今日も今日とて爆益モーニングかましました👊」
例：「若松7R🎯46🎯4,530円🎯2単パワー💪本線万舟やったぞ」
例：「芦屋9R🎯124🎯1,780円ブンブーーン抑え大事1-2=3熱男やったぞ」
フォーマット: [レース場][レース番号]R🎯[的中目]🎯[払戻金]円[絵文字][自由に熱い一言や考察の振り返り]

プラットフォーム（note, x, line）ごとに、後半の【熱い一言】の部分だけ少しテイストを変えて、冒頭の基本フォーマットは揃えてください。
JSON形式で出力してください:
{{
    "note": "note用テキスト",
    "x": "X用テキスト",
    "line": "LINE用テキスト"
}}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error generating doya post: {e}")
            return {"note": "生成失敗", "x": "生成失敗", "line": "生成失敗"}


if __name__ == "__main__":
    load_dotenv()
    checker = ResultChecker()

    # テスト: 予想記事から買い目を抽出
    test_article = """
15:30〆 🔥蒲郡12R勝負🔥

桐生さんのロケットスタート🚀に期待！💥

本線
3-1-2
3-2-1
3-1-4
3-4-1

熱男スペシャル💎
3-1-2
3-2-1

抑え
3-2-4
"""
    bets = checker.parse_bets_from_article(test_article)
    print("=== 抽出された買い目 ===")
    print(json.dumps(bets, ensure_ascii=False, indent=2))

    # テスト: 的中判定（結果が 3-1-2 だった場合）
    result_order = ["3", "1", "2"]
    hit = checker.check_hit(bets, result_order)
    print("\n=== 的中判定 ===")
    print(json.dumps(hit, ensure_ascii=False, indent=2))

    # テスト: ドヤ投稿生成
    if hit["is_hit"]:
        race_info = {"venue": "蒲郡", "race_no": 12}
        doya = checker.generate_doya_post(hit, race_info)
        print("\n=== ドヤ投稿 ===")
        print(json.dumps(doya, ensure_ascii=False, indent=2))
