"""
BoatAuto Web UI (Streamlit)
"""
import os
import sys
import json
import glob
from datetime import datetime
import pytz
import streamlit as st
from dotenv import load_dotenv

PENDING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending_bets")
if not os.path.exists(PENDING_DIR):
    os.makedirs(PENDING_DIR)

def load_pending() -> list:
    bets = []
    for filepath in glob.glob(os.path.join(PENDING_DIR, "*.json")):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                bet = json.load(f)
                bets.append(bet)
        except Exception:
            pass
    # 日付・時間順にソート (新しいものが上)
    bets.sort(key=lambda x: (x.get("date", ""), x.get("deadline", "")), reverse=True)
    return bets

def save_pending_item(bet: dict):
    filepath = os.path.join(PENDING_DIR, f"{bet['key']}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(bet, f, ensure_ascii=False, indent=2)

def add_pending(program: dict, article: str):
    key = f"{program['jcd']}_{program['race_no']}_{program.get('date', '')}"
    
    # 既存のファイルがあれば読み込んでステータスを引き継ぐ
    status = "pending"
    filepath = os.path.join(PENDING_DIR, f"{key}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                old_bet = json.load(f)
                status = old_bet.get("status", "pending")
        except Exception:
            pass

    bet = {
        "key": key,
        "venue": program["venue"],
        "race_no": program["race_no"],
        "jcd": program["jcd"],
        "date": program.get("date", ""),
        "deadline": program.get("deadline", ""),
        "article": article,
        "saved_at": datetime.now(pytz.timezone('Asia/Tokyo')).strftime("%H:%M"),
        "status": status
    }
    save_pending_item(bet)

def mark_pending_checked(key: str, is_hit: bool):
    filepath = os.path.join(PENDING_DIR, f"{key}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                bet = json.load(f)
            bet["status"] = "hit" if is_hit else "miss"
            save_pending_item(bet)
        except Exception:
            pass

def delete_pending(key: str):
    filepath = os.path.join(PENDING_DIR, f"{key}.json")
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception:
            pass


sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.scraper import KyoteiScraper
from src.ai_generator import AIGenerator
from src.publisher import Publisher
from src.result_checker import ResultChecker

# ==========================================
# ページ設定
# ==========================================
st.set_page_config(
    page_title="BoatAuto",
    page_icon="🚤",
    layout="wide",
    initial_sidebar_state="expanded",
)

# セッションステートの初期化
if "program" not in st.session_state:
    st.session_state.program = None
if "article" not in st.session_state:
    st.session_state.article = None
if "promo" not in st.session_state:
    st.session_state.promo = None
if "hit_result" not in st.session_state:
    st.session_state.hit_result = None
if "daily_hits" not in st.session_state:
    st.session_state.daily_hits = []
if "pending_check_key" not in st.session_state:
    st.session_state.pending_check_key = None
if "pending_article" not in st.session_state:
    st.session_state.pending_article = None
if "pending_program" not in st.session_state:
    st.session_state.pending_program = None

# ==========================================
# ロード処理
# ==========================================
@st.cache_resource
def load_modules():
    load_dotenv()
    scraper = KyoteiScraper()
    ai = AIGenerator()
    publisher = Publisher()
    checker = ResultChecker()
    return scraper, ai, publisher, checker

try:
    scraper, ai, publisher, checker = load_modules()
except Exception as e:
    st.error(f"モジュールの初期化に失敗しました: {e}")
    st.stop()

# ==========================================
# UI: サイドバー (設定・操作パネル)
# ==========================================
with st.sidebar:
    st.title("🚤 BoatAuto 設定")
    
    if st.button("↻ 画面を更新", use_container_width=True):
        st.rerun()
    
    # ペルソナ選択
    personas = ai.get_available_personas()
    selected_persona = st.selectbox("📝 ペルソナ（口調）", personas)
    
    st.divider()
    
    # レース場選択 / 直近のレース
    st.subheader("1. レース選択")
    
    @st.cache_data(ttl=60) # 1分間キャッシュ
    def cached_get_upcoming():
        return scraper.get_upcoming_races(max_minutes=30)
        
    upcoming_races = cached_get_upcoming()
    
    # 選択状態を保持するためのセッションステート
    if "selected_jcd" not in st.session_state:
        if upcoming_races:
            first_upc = upcoming_races[0]
            st.session_state.selected_jcd = first_upc['jcd']
            st.session_state.selected_venue_name = first_upc['venue']
            st.session_state.selected_race_no = first_upc['race_no']
        else:
            st.session_state.selected_jcd = "01"
            st.session_state.selected_venue_name = "桐生"
            st.session_state.selected_race_no = 12
    
    with st.expander("⏱️ 直近のレース一覧 (締切30分以内)", expanded=True):
        if not upcoming_races:
            st.info("現在30分以内に締切を迎えるレースはありません。")
        else:
            for race in upcoming_races:
                btn_label = f"{race['deadline']}〆 {race['venue']} {race['race_no']}R (残り{race['minutes_left']}分)"
                if st.button(btn_label, key=f"upc_{race['jcd']}_{race['race_no']}"):
                    st.session_state.selected_jcd = race['jcd']
                    st.session_state.selected_venue_name = race['venue']
                    st.session_state.selected_race_no = race['race_no']
                    st.success(f"選択: {race['venue']} {race['race_no']}R")
    
    st.markdown("---")
    st.markdown("**手動での指定**")
    @st.cache_data(ttl=3600)
    def cached_get_venues():
        return scraper.get_race_list()
    
    venues = cached_get_venues()
    if venues:
        venue_options = {v['name']: v for v in venues}
        # セッションステートの選択値を反映させるためのインデックス探し
        default_venue_idx = 0
        for idx, v in enumerate(venues):
            if v['jcd'] == st.session_state.selected_jcd:
                default_venue_idx = idx
                break
                
        selected_venue_label = st.selectbox("📍 レース場", list(venue_options.keys()), index=default_venue_idx)
        selected_venue = venue_options[selected_venue_label]
        
        # セッションステートのレース番号
        race_choices = [f"{i}R" for i in range(1, 13)]
        default_race_idx = st.session_state.selected_race_no - 1
        if not (0 <= default_race_idx <= 11): default_race_idx = 11
        selected_race_str = st.selectbox("🏁 レース番号", race_choices, index=default_race_idx)
        selected_race_no = int(selected_race_str.replace("R", ""))
        
        # 手動選択結果をセッションに反映
        st.session_state.selected_jcd = selected_venue["jcd"]
        st.session_state.selected_venue_name = selected_venue["name"]
        st.session_state.selected_race_no = selected_race_no
        
    else:
        st.error("本日の開催場が見つかりません。")
        st.stop()
        
    # 出走表取得ボタン
    if st.button("📊 出走表を取得", use_container_width=True, type="primary"):
        with st.spinner("出走表を取得中..."):
            program = scraper.get_race_program(jcd=st.session_state.selected_jcd, race_no=st.session_state.selected_race_no)
            if program and program.get("entries"):
                st.session_state.program = program
                st.session_state.article = None
                st.session_state.hit_result = None
                st.success("出走表を取得しました！")
            else:
                st.error("出走表の取得に失敗しました。")

    st.divider()
    
    # 生成オプション
    st.subheader("2. 生成オプション")
    
    fixed_first_col, char_col = st.columns(2)
    with fixed_first_col:
        fixed_first_options = ["指定なし", "1", "2", "3", "4", "5", "6"]
        ff_str = st.selectbox("1着固定", fixed_first_options)
        fixed_first = int(ff_str) if ff_str != "指定なし" else None
        
    with char_col:
        char_max = st.number_input("最大文字数", min_value=10, max_value=500, value=200, step=10)
        
    st.caption("買い目点数")
    honsen_max = st.number_input("本線 最大点数", min_value=1, max_value=20, value=6, step=1)
    atsuo_max = st.number_input("熱男 最大点数", min_value=0, max_value=6, value=2, step=1)
    osae_max = st.number_input("抑え 最大点数", min_value=0, max_value=10, value=2, step=1)
    
    # 記事生成ボタン
    if st.button("🤖 AI予想記事を生成", use_container_width=True, type="primary"):
        if not st.session_state.program:
            st.warning("先に出走表を取得してください！")
        else:
            with st.spinner("AIが記事を執筆中..."):
                options = {
                    "deadline": st.session_state.program.get("deadline", "未定"),
                    "char_min": 10,
                    "char_max": char_max,
                    "fixed_first": fixed_first,
                    "bet_honsen_min": 2,
                    "bet_honsen_max": honsen_max,
                    "bet_atsuo_min": 0,
                    "bet_atsuo_max": atsuo_max,
                    "bet_osae_min": 0,
                    "bet_osae_max": osae_max,
                }
                
                # 記事生成
                article = ai.generate_note_article(
                    st.session_state.program, 
                    persona_name=selected_persona, 
                    options=options
                )
                # SNSプロモ生成
                promo = ai.generate_sns_promo(
                    article, 
                    persona_name=selected_persona, 
                    options=options
                )
                
                st.session_state.article = article
                st.session_state.promo = promo
                st.session_state.hit_result = None
                st.success("記事が完成しました！")

# ==========================================
# UI: メインエリア
# ==========================================
st.title("🚤 BoatAuto Dashboard")

# 1. 出走表表示エリア
if st.session_state.program:
    p = st.session_state.program
    st.header(f"📊 {p['venue']} {p['race_no']}R 出走表")
    st.caption(f"締切予定: {p.get('deadline', '未定')}")
    
    # テーブル表示用のデータ整形
    table_data = []
    for entry in p["entries"]:
        table_data.append({
            "枠": entry["waku"],
            "選手名": entry["name"],
            "登番": entry.get("toban", ""),
            "級別": entry.get("class", ""),
            "支部": entry.get("branch", ""),
        })
    st.table(table_data)
else:
    st.info("👈 サイドバーからレースを選択して「出走表を取得」を押してください。")

st.divider()

# 2. 生成結果エリア
if st.session_state.article:
    st.header("📝 生成されたテキスト")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("note用 予想記事")
        
        def update_article():
            st.session_state.article = st.session_state.edit_article

        st.text_area("内容を確認・編集できます:", value=st.session_state.article, height=400, key="edit_article", on_change=update_article)
        
        save_col1, save_col2 = st.columns(2)
        with save_col1:
            if st.button("💾 記事をファイルに保存", use_container_width=True):
                output_dir = os.path.join(os.path.dirname(__file__), "output")
                os.makedirs(output_dir, exist_ok=True)
                p = st.session_state.program
                file_path = os.path.join(output_dir, f"{p['venue']}{p['race_no']}R_article.txt")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(st.session_state.edit_article)
                # ファイル保存と同時に保留リストにも自動追加
                add_pending(st.session_state.program, st.session_state.edit_article)
                st.success(f"✅ 保存しました！保留リストにも追加済みです。ブラウザを閉じても後で結果確認できます。")

        with save_col2:
            if st.button("🔒 予想を保留する（後で結果確認）", use_container_width=True, type="primary"):
                add_pending(st.session_state.program, st.session_state.edit_article)
                p = st.session_state.program
                st.success(f"✅ {p['venue']}{p['race_no']}R を保留リストに追加しました！ブラウザを閉じても大丈夫です。")
            
    with col2:
        st.subheader("SNS用 告知文")
        
        st.markdown("**LINEオープンチャット用**")
        line_text = st.session_state.promo.get("line_post", "")
        st.info(line_text)
        if st.button("📋 LINE用をクリップボードにコピー", key="copy_line"):
            publisher.post_to_line_opchat(line_text)
            st.success("コピーしました！")
            
        st.markdown("**X (Twitter) 用**")
        x_text = st.session_state.promo.get("x_post", "")
        st.info(x_text)

# 3. 保留中の予想リスト
st.divider()
st.header("📌 保留中の予想")
pending_bets = load_pending()
if not pending_bets:
    st.info("保留中の予想はありません。")
else:
    for bet in pending_bets:
        vkey = bet["key"]
        status = bet.get("status", "pending")
        if status == "hit":
            status_icon = "🎯 的中確認済"
        elif status == "miss":
            status_icon = "❌ ハズレ確認済"
        else:
            status_icon = "⏳ 未確認"
            
        label = f"**{bet['venue']}{bet['race_no']}R** (締切: {bet.get('deadline','??')}) ─ {bet.get('saved_at','')}保存 [{status_icon}]"
        with st.expander(label, expanded=False):
            st.code(bet["article"][:300] + "…", language="text")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🏁 結果確認する", key=f"check_{vkey}", type="primary"):
                    st.session_state.pending_check_key = vkey
                    st.session_state.pending_article = bet["article"]
                    st.session_state.pending_program = bet
                    st.session_state.hit_result = None
            with col_b:
                if st.button("🗑️ 削除", key=f"del_{vkey}"):
                    delete_pending(vkey)
                    st.rerun()

# --- 保留レースの結果確認処理 ---
if st.session_state.pending_check_key:
    pb = st.session_state.pending_program
    st.subheader(f"🏁 {pb['venue']}{pb['race_no']}R 結果確認中...")
    with st.spinner("結果を取得中..."):
        result = scraper.get_race_result(jcd=pb["jcd"], race_no=pb["race_no"], date_str=pb.get("date"))
        if result and result.get("order"):
            order_str = "-".join(result["order"][:3])
            st.write(f"**確定着順:** {order_str}")
            bets = checker.parse_bets_from_article(st.session_state.pending_article)
            hit = checker.check_hit(bets, result)
            st.session_state.hit_result = {
                "hit": hit,
                "order": order_str,
                "result_data": result,
                "program": pb,
                "from_pending": True,
            }
            # 確認済みのため状態を更新して、保留からは消さない
            mark_pending_checked(st.session_state.pending_check_key, hit["is_hit"])
            st.session_state.pending_check_key = None
        else:
            st.warning("まだ結果が出ていないようです。少し待ってから再度お試しください。")
            st.session_state.pending_check_key = None

# 4. 結果確認・ドヤ投稿エリア（現在セッション or 保留確認分）
st.divider()
st.header("🎯 結果確認＆ドヤ投稿")

if st.session_state.article and not st.session_state.hit_result:
    st.write("レース終了後、以下のボタンを押して結果を取得し、的中判定を行います。")
    if st.button("🏁 レース結果を取得して的中判定", type="primary"):
        with st.spinner("結果を取得中..."):
            p = st.session_state.program
            result = scraper.get_race_result(jcd=p["jcd"], race_no=p["race_no"])
            if result and result.get("order"):
                order_str = "-".join(result["order"][:3])
                st.write(f"**確定着順:** {order_str}")
                bets = checker.parse_bets_from_article(st.session_state.edit_article)
                hit = checker.check_hit(bets, result)
                st.session_state.hit_result = {
                    "hit": hit,
                    "order": order_str,
                    "result_data": result,
                    "program": st.session_state.program,
                }
            else:
                st.warning("レース結果の取得に失敗しました。まだレースが終わっていない可能性があります。")

if st.session_state.hit_result:
    hit_data = st.session_state.hit_result
    hit = hit_data["hit"]
    
    if hit["is_hit"]:
        section_name_map = {"honsen": "本線", "atsuo": "熱男（絞り）", "osae": "抑え"}
        section_ja = section_name_map.get(hit.get('hit_section', ''), hit.get('hit_section', '不明'))
        st.success(f"🎉🎉🎉 的中しました！ ({section_ja} で {hit.get('hit_bet', '')}) 🎉🎉🎉")
        
        with st.spinner("ドヤ投稿を生成中..."):
            p = hit_data["program"]
            race_info = {"venue": p["venue"], "race_no": p["race_no"]}
            doya = checker.generate_doya_post(hit, race_info, persona_name=selected_persona)
            
            # ユーザー指定の厳密フォーマット
            simple_doya = f"{p['venue']}{p['race_no']}R🎯{hit.get('result_str', '').replace('-','')}🎯{hit.get('payout', 0):,}円🛵💨"
            
            # 本日の的中リストに追加 (重複防止)
            if simple_doya not in st.session_state.daily_hits:
                st.session_state.daily_hits.append(simple_doya)
            
            st.subheader("🔥 的中ドヤ報告 (コピペ用)")
            st.code(simple_doya, language="text")
            
            with st.expander("📝 SNS用 長文ドヤテキスト (AI生成)"):
                dk_col1, dk_col2 = st.columns(2)
                with dk_col1:
                    st.markdown("**note用 / X用**")
                    st.info(doya.get("note", ""))
                    st.info(doya.get("x", ""))
                with dk_col2:
                    st.markdown("**LINE用**")
                    line_doya = doya.get("line", "")
                    st.info(line_doya)
                    if st.button("📋 ドヤ文字をコピー", key=f"copy_{p['venue']}_{p['race_no']}"):
                        publisher.post_to_line_opchat(line_doya)
                        st.success("コピーしました！")
    else:
        st.error(f"😢 残念... ハズレです (結果: {hit_data['order']})")

if st.session_state.daily_hits:
    st.divider()
    st.header("🏆 本日の的中リスト")
    
    hits_text = "\n".join(st.session_state.daily_hits)
    st.code(hits_text, language="text")
    
    if st.button("📋 中間報告用に全リストをコピー", key="copy_daily_hits"):
        publisher.post_to_line_opchat(hits_text)
        st.success("コピーしました！")
