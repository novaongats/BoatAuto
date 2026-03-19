import sys
sys.path.insert(0, 'c:/Projects/BoatAuto')
from src.scraper import KyoteiScraper
import json
s = KyoteiScraper()
# 唐津1R (先ほど確認した結果あり)
r = s.get_race_result('23', 1, '20260319')
print(json.dumps(r, ensure_ascii=False, indent=2))
