import sys
sys.path.insert(0, 'c:/Projects/BoatAuto')
from src.scraper import KyoteiScraper
import json

s = KyoteiScraper()
p = s.get_race_program('23', 5, '20260319')
print("venue:", p.get('venue'))
print("deadline:", p.get('deadline'))
for e in p.get('entries', []):
    print(f"  {e['waku']}. {e['name']} [{e.get('grade','')}] ST:{e.get('avg_st')} 全国2連:{e.get('national_2ren')}% モーター{e.get('motor_no')}:{e.get('motor_2ren')}% 当地2連:{e.get('local_2ren')}%")
