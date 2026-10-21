import csv
import io
import itertools
import math
import os
import random
import re
from typing import Dict, List, Tuple
import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# ユーザー設定
TARGET_RACE_ID = "202505040911"
BET_TYPE = "三連複"
RACE_PLACE = "東京"
TRACK_TYPE = "芝"
DISTANCE = 2000
MIN_HORSE_PROB = 0.03
EV_THRESHOLD = 1.15
SOFTMAX_BETA = 0.12

FACTOR_WEIGHTS = {
    "pedigree": 2.5, "workout": 2.5, "ability": 2.0,
    "course": 1.2, "jockey": 1.0, "bias": 0.8,
}

FAVORITE_SIRES = {
    "ディープインパクト": 8.5, "ロードカナロア": 8.0, "ハーツクライ": 8.0,
    "キズナ": 7.5, "エピファネイア": 7.5, "ドゥラメンテ": 7.5,
    "モーリス": 7.0, "ゴールドシップ": 7.0,
}

CSV_FILE_PATH = f"factor_sheet_{TARGET_RACE_ID}.csv"
GOOGLE_SHEET_CSV_URL = ""

def auto_score_pedigree(pedigree_text: str) -> float:
    for sire, score in FAVORITE_SIRES.items():
        if sire in pedigree_text: return score
    return 5.0

def auto_score_workout(memo_text: str) -> float:
    memo = str(memo_text).lower()
    if any(w in memo for w in ["自己ベスト", "抜群", "絶好", "破格", "鋭い"]): return 9.0
    elif any(w in memo for w in ["好気配", "上々", "順調", "好調", "先着", "強め"]): return 8.0
    elif any(w in memo for w in ["馬なり", "軽快", "併走"]): return 7.0
    elif any(w in memo for w in ["重い", "モタモタ", "遅れ", "余裕ない"]): return 4.0
    elif any(w in memo for w in ["凡庸", "平凡", "重苦しい"]): return 3.5
    return 5.0

def auto_score_ability(prev_rank_str: str, time_diff_str: str) -> float:
    try:
        diff = float(time_diff_str)
        if diff <= 0.0: return 9.0
        elif diff <= 0.2: return 8.0
        elif diff <= 0.5: return 6.5
        elif diff <= 0.9: return 5.0
        else: return 3.5
    except ValueError:
        try:
            rank = int(prev_rank_str)
            if rank == 1: return 8.5
            elif rank <= 3: return 7.5
            elif rank <= 5: return 6.0
            elif rank <= 9: return 5.0
            else: return 3.5
        except ValueError:
            return 5.0

def apply_track_and_course_bias(waku_str: str, place: str, track_type: str, distance: int) -> float:
    base_score = 5.0
    try: waku = int(waku_str)
    except ValueError: return base_score
    if place in ["中山", "福島", "小倉", "函館", "札幌"] and track_type == "芝":
        if waku in (1, 2, 3): base_score = 7.5
        elif waku in (7, 8): base_score = 4.0
    elif place in ["東京", "新潟", "阪神"] and track_type == "芝":
        if waku in (7, 8) and distance >= 1800: base_score = 6.5
        elif waku in (1, 2): base_score = 6.0
    elif track_type == "ダ":
        if waku in (1, 2, 3, 4): base_score = 6.5
        else: base_score = 4.5
    return base_score

def fetch_and_create_base_csv(race_id: str, csv_path: str) -> bool:
    url = f"https://race.netkeiba.com/race/shutuba_past.html?race_id={race_id}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = resp.apparent_encoding
        if resp.status_code != 200: return False
    except Exception:
        return False

    soup = BeautifulSoup(resp.text, "lxml")
    horse_rows = soup.select("tr.HorseList")
    if not horse_rows: return False

    horses_data = []
    for idx, tr in enumerate(horse_rows, start=1):
        name_elem = tr.select_one(".Horse02 a, .HorseName a")
        if not name_elem:
            continue
        waku_td = tr.select_one("td[class^='Waku']")
        umaban_td = tr.select_one("td[class^='Umaban']")
        waku = waku_td.get_text(strip=True) if waku_td else "-"
        umaban_text = umaban_td.get_text(strip=True) if umaban_td else ""
        horse_num = int(umaban_text) if umaban_text.isdigit() else idx
        horse_name = name_elem.get_text(strip=True)
        jockey_elem = tr.select_one("td.Jockey a")
        jockey_name = jockey_elem.get_text(strip=True) if jockey_elem else "未定"
        sire_elem = tr.select_one(".Borei, .Blood, td.HorseInfo")
        pedigree_text = sire_elem.get_text(" ", strip=True) if sire_elem else ""
        past_td = tr.select_one("td.Past")
        prev_rank, prev_diff = "-", "-"
        if past_td:
            rank_elem = past_td.select_one(".Num")
            if rank_elem: prev_rank = rank_elem.get_text(strip=True)
            diff_match = re.search(r"\(([-+]?\d+\.\d+)\)", past_td.get_text(" ", strip=True))
            if diff_match: prev_diff = diff_match.group(1)

        horses_data.append({
            "horse_num": horse_num, "waku": waku if waku else "-", "name": horse_name,
            "jockey": jockey_name, "prev_info": f"{prev_rank}着(差:{prev_diff}s)",
            "pedigree": auto_score_pedigree(pedigree_text), "workout": 5.0,
            "workout_memo": "特になし", "ability": auto_score_ability(prev_rank, prev_diff),
            "course": 5.0, "jockey_score": 5.0, "bias": apply_track_and_course_bias(waku, RACE_PLACE, TRACK_TYPE, DISTANCE),
        })

    horses_data.sort(key=lambda x: x["horse_num"])
    fieldnames = ["horse_num", "waku", "name", "jockey", "prev_info", "pedigree", "workout", "workout_memo", "ability", "course", "jockey_score", "bias"]
    with open(csv_path, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(horses_data)
    return True

def load_factor_table(csv_path: str, gsheet_url: str = "") -> Dict[int, Dict]:
    grade_map = {"S": 9.5, "A": 8.0, "B": 6.0, "C": 4.0, "◎": 9.0, "○": 8.0, "▲": 7.0, "△": 6.0}
    def parse_score(val_str: str) -> float:
        v = str(val_str).strip().upper()
        if v in grade_map: return grade_map[v]
        try: return float(v)
        except ValueError: return 5.0

    f_obj = io.StringIO(requests.get(gsheet_url, timeout=10).text) if gsheet_url else open(csv_path, mode="r", encoding="utf-8-sig")
    factor_table = {}
    with f_obj as f:
        for row in csv.DictReader(f):
            h_num = int(row["horse_num"])
            raw_w = row.get("workout", "")
            w_memo = row.get("workout_memo", "")
            w_score = auto_score_workout(w_memo) if not raw_w or raw_w == "5.0" else parse_score(raw_w)
            factor_table[h_num] = {
                "name": row.get("name", f"馬番{h_num}"),
                "pedigree": parse_score(row.get("pedigree", 5.0)),
                "workout": w_score,
                "ability": parse_score(row.get("ability", 5.0)),
                "course": parse_score(row.get("course", 5.0)),
                "jockey": parse_score(row.get("jockey_score", 5.0)),
                "bias": parse_score(row.get("bias", 5.0)),
            }
    return factor_table

def calculate_scores_and_win_probs(factor_table, weights, beta=0.12):
    total_scores = {h: sum(f.get(k, 5.0) * w for k, w in weights.items()) for h, f in factor_table.items()}
    max_s = max(total_scores.values())
    exp_s = {h: math.exp(beta * (s - max_s)) for h, s in total_scores.items()}
    sum_exp = sum(exp_s.values())
    return total_scores, {h: val / sum_exp for h, val in exp_s.items()}

def calc_exacta_prob(p1, p2): return p1 * (p2 / (1.0 - p1)) if (1.0 - p1) > 0 else 0.0
def calc_trifecta_prob(p1, p2, p3):
    if (1.0 - p1) <= 0 or (1.0 - p1 - p2) <= 0: return 0.0
    return p1 * (p2 / (1.0 - p1)) * (p3 / (1.0 - p1 - p2))

def calc_combination_probs(win_probs, bet_type, horses):
    comb_probs = {}
    if bet_type == "馬連":
        for h1, h2 in itertools.combinations(sorted(horses), 2):
            comb_probs[(h1, h2)] = calc_exacta_prob(win_probs[h1], win_probs[h2]) + calc_exacta_prob(win_probs[h2], win_probs[h1])
    elif bet_type == "三連複":
        for h1, h2, h3 in itertools.combinations(sorted(horses), 3):
            comb_probs[(h1, h2, h3)] = sum(calc_trifecta_prob(win_probs[a], win_probs[b], win_probs[c]) for a, b, c in itertools.permutations((h1, h2, h3), 3))
    elif bet_type == "三連単":
        for h1, h2, h3 in itertools.combinations(sorted(horses), 3):
            comb_probs[(h1, h2, h3)] = calc_trifecta_prob(win_probs[h1], win_probs[h2], win_probs[h3])
    return comb_probs

def generate_mock_odds_by_type(win_probs, bet_type):
    takeout_rate = {"馬連": 0.225, "三連複": 0.250, "三連単": 0.275}[bet_type]
    all_comb_probs = calc_combination_probs(win_probs, bet_type, sorted(list(win_probs.keys())))
    random.seed(100)
    alpha = 0.74
    raw_votes = {comb: math.exp(-((-math.log(max(tp, 1e-9))) ** alpha)) * random.uniform(0.78, 1.28) for comb, tp in all_comb_probs.items()}
    total_votes = sum(raw_votes.values())
    net_pool = 1.0 - takeout_rate
    return {comb: max(1.1, math.floor((net_pool / (v / total_votes)) * 10) / 10.0) for comb, v in raw_votes.items()}

def select_expected_value_bets(win_probs, odds_dict, bet_type, min_horse_prob, ev_threshold):
    valid_horses = sorted([h for h, p in win_probs.items() if p >= min_horse_prob], key=lambda x: win_probs[x], reverse=True)
    min_comb_prob = {"馬連": 0.005, "三連複": 0.002, "三連単": 0.0008}[bet_type]
    comb_probs = calc_combination_probs(win_probs, bet_type, valid_horses)
    sep = "-" if bet_type in ("馬連", "三連複") else "→"
    recommended = []
    for comb, prob in comb_probs.items():
        if prob < min_comb_prob: continue
        odds = odds_dict.get(comb, 0.0)
        ev = prob * odds
        if odds > 1.0 and ev >= ev_threshold:
            recommended.append({"comb_str": sep.join(f"{h:02d}" for h in comb), "odds": odds, "fair_odds": 1.0 / prob, "ev": ev})
    recommended.sort(key=lambda x: x["ev"], reverse=True)
    return recommended, valid_horses

def main():
    print(f"=== 競馬 EV予測システム v5 ===")
    print(f"対象レースID: {TARGET_RACE_ID} | 券種: {BET_TYPE} | EV閾値: {EV_THRESHOLD}")

    if not GOOGLE_SHEET_CSV_URL:
        if not os.path.exists(CSV_FILE_PATH):
            print("CSVが見つかりません。netkeibaからスクレイピングして生成します...")
            if fetch_and_create_base_csv(TARGET_RACE_ID, CSV_FILE_PATH):
                print(f"{CSV_FILE_PATH} を生成しました。")
            else:
                print("出馬表データの取得に失敗しました。")
                return
        else:
            print(f"{CSV_FILE_PATH} は既に存在します。読み込みます。")

    try:
        factor_table = load_factor_table(CSV_FILE_PATH, GOOGLE_SHEET_CSV_URL)
        print(f"{len(factor_table)} 頭のデータを読み込みました。")
    except Exception as e:
        print(f"データ読み込みエラー: {e}")
        return

    scores, win_probs = calculate_scores_and_win_probs(factor_table, FACTOR_WEIGHTS, SOFTMAX_BETA)

    print("\n--- 【推定勝率上位】 ---")
    sorted_probs = sorted(win_probs.items(), key=lambda x: x[1], reverse=True)
    for h, p in sorted_probs[:5]:
        print(f"馬番{h:02d} ({factor_table[h]['name']}): {p*100:.1f}%")

    print(f"\n--- 模擬オッズ生成（{BET_TYPE}） ---")
    mock_odds = generate_mock_odds_by_type(win_probs, BET_TYPE)

    print("\n--- 期待値(EV) 買い目抽出 ---")
    recommended, valid_horses = select_expected_value_bets(win_probs, mock_odds, BET_TYPE, MIN_HORSE_PROB, EV_THRESHOLD)

    if recommended:
        for idx, rec in enumerate(recommended[:10], 1):
            print(f"{idx}位 | 買い目: [{rec['comb_str']}] | 模擬オッズ: {rec['odds']:5.1f}倍 | 適正オッズ: {rec['fair_odds']:5.1f}倍 | EV: {rec['ev']:.2f}")
    else:
        print(f"期待値 {EV_THRESHOLD} を超える買い目が見つかりませんでした。")

if __name__ == "__main__":
    main()
