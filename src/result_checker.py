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

    def check_hit(self, bets: Dict[str, List[str]], race_result_order: List[str]) -> Dict:
        """
        買い目とレース結果を照合して的中判定する。
        race_result_order: ["1", "3", "5"] のような着順リスト（1着, 2着, 3着）

        戻り値: {
            "is_hit": bool,
            "hit_section": "honsen" | "atsuo" | "osae" | None,
            "hit_bet": "3-1-2" | None,
            "result_str": "3-1-2"
        }
        """
        if len(race_result_order) < 3:
            return {"is_hit": False, "hit_section": None, "hit_bet": None, "result_str": ""}

        # 実際の結果を "X-Y-Z" 形式にする
        result_3tan = f"{race_result_order[0]}-{race_result_order[1]}-{race_result_order[2]}"
        result_2tan = f"{race_result_order[0]}-{race_result_order[1]}"

        hit_result = {
            "is_hit": False,
            "hit_section": None,
            "hit_bet": None,
            "result_str": result_3tan,
        }

        # 各セクションで照合（熱男 → 本線 → 抑え の順に優先度を付ける）
        for section in ["atsuo", "honsen", "osae"]:
            for bet in bets.get(section, []):
                # 3連単の完全一致
                if bet == result_3tan:
                    hit_result["is_hit"] = True
                    hit_result["hit_section"] = section
                    hit_result["hit_bet"] = bet
                    return hit_result
                # 2連単の一致（2つの数字の場合）
                parts = bet.split("-")
                if len(parts) == 2 and bet == result_2tan:
                    hit_result["is_hit"] = True
                    hit_result["hit_section"] = section
                    hit_result["hit_bet"] = bet
                    return hit_result
                # フォーメーション買い目の展開チェック (例: "5-14-146")
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
                        return hit_result

        return hit_result

    def generate_doya_post(self, hit_info: Dict, race_info: Dict, persona_name: str = "default") -> Dict[str, str]:
        """
        的中情報からドヤ投稿テキストを生成する。
        """
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
        result_str = hit_info.get("result_str", "")
        hit_bet = hit_info.get("hit_bet", "")

        user_prompt = f"""
以下の的中情報をもとに、各プラットフォーム用のドヤ投稿を作成してください。

【的中情報】
- レース場: {venue} {race_no}R
- 結果: {result_str}
- 的中した買い目: {hit_bet}（{section_name}で的中）

【出力要件】
1. note用: 2〜3行程度の短い的中報告。絵文字たっぷりで。
2. X用: 140文字以内。「的中🎯」のような熱い一言と結果。
3. LINE用: 親しみやすいトーンで仲間に報告。

JSON形式で出力:
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
