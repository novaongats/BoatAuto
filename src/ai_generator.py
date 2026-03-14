import os
import json
from openai import OpenAI
from typing import Dict, Any

class AIGenerator:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        self.client = OpenAI(api_key=self.api_key)
        self.personas_file = os.path.join(os.path.dirname(__file__), "personas.json")
        self._load_personas()

    def _load_personas(self):
        """
        ペルソナ（語り口調）の設定ファイルを読み込む。
        """
        if os.path.exists(self.personas_file):
            with open(self.personas_file, 'r', encoding='utf-8') as f:
                self.personas = json.load(f)
        else:
            # デフォルトの空のペルソナ設定
            self.personas = {
                "default": {
                    "description": "標準的な丁寧な口調",
                    "system_prompt": "あなたは競艇のプロ予想家です。丁寧な言葉遣いで、論理的にレース展開を予想してください。"
                }
            }
            # サンプルファイルを作成
            with open(self.personas_file, 'w', encoding='utf-8') as f:
                json.dump(self.personas, f, ensure_ascii=False, indent=4)

    def get_available_personas(self) -> list:
        return list(self.personas.keys())

    def generate_note_article(self, race_data: Dict, persona_name: str = "default", options: Dict = None) -> str:
        """
        レース情報をもとにnote用の予想記事を生成する。
        """
        if options is None:
            options = {}
            
        if persona_name not in self.personas:
            print(f"Warning: Persona '{persona_name}' not found. Using 'default'.")
            persona_name = "default"
            
        system_prompt = self.personas[persona_name].get("system_prompt", "")
        
        # ユーザーに渡すレースデータ（出走表など）をフォーマット
        race_info_text = json.dumps(race_data, ensure_ascii=False, indent=2)
        
        # オプションパラメータの展開
        deadline = options.get("deadline", "未定")
        char_min = options.get("char_min", 50)
        char_max = options.get("char_max", 200)
        fixed_first = options.get("fixed_first") # e.g., 3 (3号艇固定)
        
        bet_honsen_min = options.get("bet_honsen_min", 2)
        bet_honsen_max = options.get("bet_honsen_max", 8)
        bet_atsuo_min = options.get("bet_atsuo_min", 0)
        bet_atsuo_max = options.get("bet_atsuo_max", 2)
        bet_osae_min = options.get("bet_osae_min", 0)
        bet_osae_max = options.get("bet_osae_max", 4)

        bet_instruction = f"""
買い目を作成する際は以下の厳密なルールに従ってください。
- 本線は {bet_honsen_min}点 ～ {bet_honsen_max}点 の範囲で出力。
- 熱男スペシャル💎は、上で作成した「本線」の買い目の中から {bet_atsuo_min}点 ～ {bet_atsuo_max}点 に厳選して出力。
- 抑えは {bet_osae_min}点 ～ {bet_osae_max}点 の範囲で出力。
"""
        if fixed_first:
            bet_instruction += f"\n- **必ず【{fixed_first}号艇】を1着固定（アタマ）にした買い目**にしてください。本線・熱男・抑えすべて {fixed_first}号艇 が1着から始まる買い目であること。"

        user_prompt = f"""
以下の競艇レース情報を分析し、考察と買目を含む予想記事を作成してください。
冒頭は必ずタイトルの前に「{deadline}〆」という締切時間から始めてください。
考察文（レースの展開予想や見解）は必ず買い目の【前】にのみ書き、買い目の後に文章は書かないでください。
考察文の長さは全体で {char_min}文字 〜 {char_max}文字 程度に収めてください。

【レース情報】
{race_info_text}

{bet_instruction}

【出力要件・構成順序】
1. 締切時間とタイトル (例: {deadline}〆 🔥◯◯レース勝負🔥)
2. レースの展開予想・見解（短く簡潔に）
3. 買い目（本線、熱男スペシャル💎、抑え の順。以降文章を含めない）
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",  # または gpt-4-turbo
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating article: {e}")
            return "記事の生成に失敗しました。"

    def generate_sns_promo(self, article_text: str, persona_name: str = "default", options: Dict = None) -> Dict[str, str]:
        """
        note記事の宣伝用テキスト（XおよびLINE用）を生成する。
        """
        if options is None:
            options = {}
            
        deadline = options.get("deadline", "未定")
            
        system_prompt = self.personas.get(persona_name, {}).get("system_prompt", "")
        system_prompt += "\n\nまた、あなたはSNS（XとLINEオープンチャット）での告知も行います。文字数制限を意識し、クリックしたくなるような短い告知文を作成してください。"

        user_prompt = f"""
以下のnote記事の宣伝文を作成してください。
冒頭には必ず、X用・LINE用ともに「{deadline}〆」を含めてください。

X（Twitter）用は「{deadline}〆」から入り、140文字以内でハッシュタグを含め、読者の興味を惹く内容にしてください。
LINEオープンチャット用は「{deadline}〆」から入り、親しみやすい口調で記事へのリンクを促してください。

【note記事】
{article_text[:1000]}... (中略)

【出力形式】
JSON形式で出力してください。
{{
    "x_post": "X用のテキスト",
    "line_post": "LINE用のテキスト"
}}
"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                response_format={ "type": "json_object" },
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"Error generating SNS promo: {e}")
            return {"x_post": "告知の生成に失敗しました。", "line_post": "告知の生成に失敗しました。"}

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    # テスト用ダミーデータ
    dummy_race_data = {
        "jcd": "02",
        "race_no": 12,
        "entries": [
            {"waku": 1, "name": "峰 竜太", "motor_rate": 45.2},
            {"waku": 2, "name": "毒島 誠", "motor_rate": 42.1},
            {"waku": 3, "name": "桐生 順平", "motor_rate": 43.1},
        ]
    }
    
    # テスト用の設定（ユーザー要望）
    test_options = {
        "deadline": "15:30",     # 締切時間
        "char_min": 10,          # 文字数下限
        "char_max": 200,         # 文字数上限
        "fixed_first": 3,        # 3号艇1着固定
        "bet_honsen_min": 2,     # 本線点数
        "bet_honsen_max": 8,
        "bet_atsuo_min": 0,      # 熱男点数
        "bet_atsuo_max": 2,
        "bet_osae_min": 0,       # 抑え点数
        "bet_osae_max": 4
    }
    
    generator = AIGenerator()
    article = generator.generate_note_article(dummy_race_data, options=test_options)
    print("=== 生成記事 ===")
    print(article)
    
    promo = generator.generate_sns_promo(article, options=test_options)
    print("\n=== SNS投稿文 ===")
    print(json.dumps(promo, ensure_ascii=False, indent=2))
