import os
import time
import tweepy
from playwright.sync_api import sync_playwright

class Publisher:
    def __init__(self):
        # API Keys for X
        self.x_api_key = os.getenv("X_API_KEY")
        self.x_api_secret = os.getenv("X_API_SECRET")
        self.x_access_token = os.getenv("X_ACCESS_TOKEN")
        self.x_access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
        
        # note Login
        self.note_email = os.getenv("NOTE_EMAIL")
        self.note_password = os.getenv("NOTE_PASSWORD")

    def create_note_draft(self, title: str, content: str) -> str:
        """
        Playwrightを使用してnoteにログインし、記事を下書きとして保存する。
        """
        if not self.note_email or not self.note_password:
            print("Note credentials not found. Skipping note draft creation.")
            return "Credentials missing"

        print(f"Creating note draft: {title}")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False) # デバッグ時はTrueにするか検討
                context = browser.new_context()
                page = context.new_page()
                
                # noteログインページへ
                page.goto("https://note.com/login")
                
                # メールアドレスとパスワード入力
                page.fill('input[name="login"]', self.note_email)
                page.fill('input[name="password"]', self.note_password)
                page.click('button:has-text("ログイン")')
                
                # ログイン完了を待機
                page.wait_for_url("https://note.com/*")
                time.sleep(2)
                
                # 記事作成ページへ
                page.goto("https://editor.note.com/drafts/new/")
                time.sleep(3)
                
                # タイトルと本文の入力 (具体的なセレクタは実際のDOMに合わせて調整が必要)
                # 例として一般的なテキストエディタの入力方法
                page.fill('[placeholder="記事タイトル"]', title) # TODO: 実際のセレクタ確認
                page.fill('[contenteditable="true"]', content) # TODO: 実際のセレクタ確認
                
                # 下書き保存されるまで少し待機（noteは自動保存される）
                time.sleep(3)
                
                browser.close()
                print("Draft created successfully (Simulated/Partial implementation)")
                return "Success"
        except Exception as e:
            print(f"Error creating note draft: {e}")
            return f"Error: {e}"

    def post_to_x(self, text: str) -> bool:
        """
        X APIを使用してテキストを投稿する。
        """
        if not all([self.x_api_key, self.x_api_secret, self.x_access_token, self.x_access_token_secret]):
            print("X API credentials not fully provided. Skipping X post.")
            # ファイル等に保存しておく代替動作
            with open("x_post_draft.txt", "w", encoding="utf-8") as f:
                f.write(text)
            return False

        try:
            client = tweepy.Client(
                consumer_key=self.x_api_key,
                consumer_secret=self.x_api_secret,
                access_token=self.x_access_token,
                access_token_secret=self.x_access_token_secret
            )
            response = client.create_tweet(text=text)
            print(f"Tweet successful: {response.data}")
            return True
        except Exception as e:
            print(f"Error posting to X: {e}")
            return False

    def post_to_line_opchat(self, text: str) -> bool:
        """
        LINEオープンチャットへ投稿する（PC版LINEアプリまたはChrome拡張の自動操作を想定）。
        フェーズ1では、手動コピペ用にテキストファイルに保存 または クリップボードにコピー
        """
        print("Saving LINE OpenChat text for manual posting (Phase 1).")
        import pyperclip
        try:
            pyperclip.copy(text)
            print("LINE text copied to clipboard.")
            
            with open("line_post_draft.txt", "w", encoding="utf-8") as f:
                f.write(text)
            return True
        except Exception as e:
            print(f"Error saving LINE text to clipboard: {e}")
            return False

if __name__ == "__main__":
    pub = Publisher()
    pub.post_to_line_opchat("今日の予想記事はこちら！\nhttps://note.com/...")
