"""
BoatAuto メインスクリプト
競艇予想の自動化フロー:
  ① レース情報取得 → ② AI記事生成 → ③ 投稿(半自動) → ④ 結果確認 → ⑤ 的中報告
"""
import os
import sys
import json
import time
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.scraper import KyoteiScraper
from src.ai_generator import AIGenerator
from src.publisher import Publisher
from src.result_checker import ResultChecker


def select_from_list(items, label="項目"):
    """ユーザーにリストから選択させるヘルパー"""
    for i, item in enumerate(items):
        print(f"  [{i+1}] {item}")
    while True:
        try:
            choice = int(input(f"\n{label}を選んでください (番号): "))
            if 1 <= choice <= len(items):
                return items[choice - 1]
        except (ValueError, EOFError):
            pass
        print("無効な入力です。もう一度入力してください。")


def main():
    print("=" * 50)
    print("  🚤 BoatAuto - 競艇予想自動化システム 🚤")
    print("=" * 50)

    load_dotenv()

    # モジュール初期化
    try:
        scraper = KyoteiScraper()
        ai = AIGenerator()
        publisher = Publisher()
        checker = ResultChecker()
    except Exception as e:
        print(f"❌ 初期化エラー: {e}")
        return

    # ペルソナ選択
    personas = ai.get_available_personas()
    print(f"\n📝 利用可能なペルソナ: {personas}")
    selected_persona = personas[0] if len(personas) == 1 else select_from_list(personas, "ペルソナ")
    print(f"✅ ペルソナ: {selected_persona}")

    # ========= Phase 1: データ取得 =========
    print("\n" + "=" * 50)
    print("  Phase 1: レースデータ取得")
    print("=" * 50)

    venues = scraper.get_race_list()
    if not venues:
        print("❌ 本日のレースがありません。")
        return

    venue_labels = [f"{v['name']}（{v['title']}）" for v in venues]
    print(f"\n🏁 本日の開催場 ({len(venues)}場):")
    selected_label = select_from_list(venue_labels, "レース場")
    selected_venue = venues[venue_labels.index(selected_label)]
    jcd = selected_venue["jcd"]
    print(f"✅ 選択: {selected_venue['name']}")

    # レース番号選択
    race_choices = [f"{i}R" for i in range(1, 13)]
    selected_race = select_from_list(race_choices, "レース番号")
    race_no = int(selected_race.replace("R", ""))

    print(f"\n📊 {selected_venue['name']} {race_no}R の出走表を取得中...")
    program = scraper.get_race_program(jcd=jcd, race_no=race_no)
    if not program or not program.get("entries"):
        print("❌ 出走表の取得に失敗しました。")
        return

    print(f"✅ 締切: {program.get('deadline', '不明')}")
    print("📋 出走表:")
    for entry in program["entries"]:
        print(f"  {entry['waku']}号艇: {entry['name']} (登録番号: {entry.get('toban', '?')})")

    # ========= Phase 2: AI記事生成 =========
    print("\n" + "=" * 50)
    print("  Phase 2: AI予想記事生成")
    print("=" * 50)

    # 生成オプション設定
    print("\n⚙️  生成オプションを設定します:")
    try:
        fixed_first_input = input("1着固定する号艇 (1-6, なしは0): ").strip()
        fixed_first = int(fixed_first_input) if fixed_first_input and fixed_first_input != "0" else None

        char_max_input = input("考察文の最大文字数 (デフォルト200): ").strip()
        char_max = int(char_max_input) if char_max_input else 200

        honsen_max_input = input("本線の最大点数 (デフォルト6): ").strip()
        honsen_max = int(honsen_max_input) if honsen_max_input else 6
    except (ValueError, EOFError):
        fixed_first = None
        char_max = 200
        honsen_max = 6

    options = {
        "deadline": program.get("deadline", "未定"),
        "char_min": 10,
        "char_max": char_max,
        "fixed_first": fixed_first,
        "bet_honsen_min": 2,
        "bet_honsen_max": honsen_max,
        "bet_atsuo_min": 0,
        "bet_atsuo_max": 2,
        "bet_osae_min": 0,
        "bet_osae_max": 4,
    }

    print(f"\n🤖 AI記事を生成中... (ペルソナ: {selected_persona})")
    article = ai.generate_note_article(program, persona_name=selected_persona, options=options)
    print("\n" + "-" * 40)
    print(article)
    print("-" * 40)

    # SNSプロモ文生成
    print("\n📱 SNS投稿文を生成中...")
    promo = ai.generate_sns_promo(article, persona_name=selected_persona, options=options)
    print(f"\n【LINE用】: {promo.get('line_post', '生成失敗')}")

    # ========= Phase 3: 投稿 (半自動) =========
    print("\n" + "=" * 50)
    print("  Phase 3: 投稿準備 (フェーズ1: 半自動)")
    print("=" * 50)

    # 記事と投稿文をファイルに保存
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    race_label = f"{selected_venue['name']}{race_no}R"
    article_path = os.path.join(output_dir, f"{race_label}_article.txt")
    with open(article_path, "w", encoding="utf-8") as f:
        f.write(article)
    print(f"📄 記事を保存: {article_path}")

    line_path = os.path.join(output_dir, f"{race_label}_line.txt")
    with open(line_path, "w", encoding="utf-8") as f:
        f.write(promo.get("line_post", ""))
    print(f"📄 LINE用テキストを保存: {line_path}")

    # LINEクリップボードコピー
    publisher.post_to_line_opchat(promo.get("line_post", ""))

    print("\n✅ Phase 3 完了！")
    print("   - noteの下書きは手動で貼り付けてください")
    print(f"   - 記事ファイル: {article_path}")
    print("   - LINEテキストはクリップボードにコピー済み")

    # ========= Phase 4: 結果待ち & 的中判定 =========
    print("\n" + "=" * 50)
    print("  Phase 4: レース結果確認 & 的中判定")
    print("=" * 50)

    input("\n⏳ レース終了後、Enterキーを押して結果を取得してください...")

    print(f"📊 {race_label} の結果を取得中...")
    result = scraper.get_race_result(jcd=jcd, race_no=race_no)

    if result and result.get("order"):
        print(f"🏆 着順: {'-'.join(result['order'][:3])}")

        # 買い目を記事から抽出して判定
        bets = checker.parse_bets_from_article(article)
        hit = checker.check_hit(bets, result["order"][:3])

        if hit["is_hit"]:
            section_names = {"honsen": "本線", "atsuo": "熱男スペシャル💎", "osae": "抑え"}
            print(f"\n🎯🎯🎯 的中！！！🎯🎯🎯")
            print(f"  {section_names.get(hit['hit_section'], '?')} で {hit['hit_bet']} が的中！")

            # ドヤ投稿生成
            print("\n🔥 ドヤ投稿を生成中...")
            race_info = {"venue": selected_venue["name"], "race_no": race_no}
            doya = checker.generate_doya_post(hit, race_info, persona_name=selected_persona)

            print(f"\n【note用】: {doya.get('note', '')}")
            print(f"【X用】: {doya.get('x', '')}")
            print(f"【LINE用】: {doya.get('line', '')}")

            # ドヤ投稿をファイルに保存
            doya_path = os.path.join(output_dir, f"{race_label}_doya.txt")
            with open(doya_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(doya, ensure_ascii=False, indent=2))
            print(f"\n📄 ドヤ投稿を保存: {doya_path}")

            # LINEクリップボードコピー
            publisher.post_to_line_opchat(doya.get("line", ""))
        else:
            print(f"\n😢 残念、今回はハズレ... 結果: {hit['result_str']}")
    else:
        print("❌ レース結果の取得に失敗しました (まだレースが終わっていない可能性があります)。")

    print("\n" + "=" * 50)
    print("  🏁 BoatAuto 完了！")
    print("=" * 50)


if __name__ == "__main__":
    main()
