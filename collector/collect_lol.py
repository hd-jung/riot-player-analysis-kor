#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect_lol_cli_v4.py — highrank 다이아 수집 fix (summonerName → by-name → puuid)
- CSV 스키마: gameId,summonerName,champion,kills,deaths,assists,teamPosition,win,kda,cs,timePlayed
- modes:
  • ids        : Riot ID(게임이름#태그) 수집
  • highrank   : 챌/그마/마스터(+옵션: 다이아) 시드 대량 수집
  • smoketest  : 단일 Riot ID로 소량 스모크 테스트
"""

import os, csv, time, argparse, sys, requests
from uuid import uuid4
from typing import List, Dict, Any, Optional, Tuple, Set
from urllib.parse import quote

# 기본 설정
DEFAULT_PLATFORM = "kr"       # league-/summoner-용 (kr/jp1/na1/euw1/…)
DEFAULT_ROUTING  = "asia"     # match-v5 라우팅 (kr/jp=asia, na=americas, eu=europe)
QUEUE            = "RANKED_SOLO_5x5"
REQUEST_GAP_SEC  = 1.2
DEFAULT_CPU      = 10

COLUMNS = ["gameId","summonerName","champion","kills","deaths","assists",
           "teamPosition","win","kda","cs","timePlayed"]

session = requests.Session()

def log(msg: str): print(msg, file=sys.stderr, flush=True)

def ensure_key(cli_key: Optional[str]) -> str:
    if cli_key: return cli_key
    ev = os.getenv("RIOT_API_KEY")
    if ev: return ev
    raise SystemExit("❌ API 키가 없습니다. --api-key 또는 RIOT_API_KEY로 제공하세요.")

def writer(path: str) -> Tuple[csv.DictWriter, Any]:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    f = open(path, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=COLUMNS)
    if f.tell() == 0: w.writeheader()
    return w, f

def seen_match_ids(path: str) -> Set[str]:
    s: Set[str] = set()
    if not os.path.exists(path): return s
    try:
        with open(path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                mid = str(r.get("gameId","")).strip()
                if mid: s.add(mid)
    except Exception as e:
        log(f"[warn] 기존 CSV 로드 실패: {e}")
    return s

def hdrs(key: str) -> Dict[str,str]: return {"X-Riot-Token": key}

# ---------- HTTP ----------
def http_json(url: str, headers: Dict[str,str], retry=6) -> Optional[Any]:
    for i in range(retry):
        try:
            r = session.get(url, headers=headers, timeout=25)
        except requests.RequestException as e:
            log(f"[req-error] {e} (retry {i+1}/{retry})"); time.sleep(1.0); continue
        if r.status_code == 200:
            return r.json()
        if r.status_code in (401,403):
            log(f"[auth] {r.status_code} 키 이슈: {r.text[:200]}"); return None
        if r.status_code in (429,503):
            wait = float(r.headers.get("Retry-After","1") or "1")
            log(f"[rate-limit] {r.status_code} → {wait:.1f}s 대기"); time.sleep(wait); continue
        if 500 <= r.status_code < 600:
            log(f"[server] {r.status_code} (retry {i+1}/{retry})"); time.sleep(1.2); continue
        log(f"[http {r.status_code}] {r.text[:200]}"); return None
    return None

# ---------- Riot API ----------
def account_by_riot_id(routing: str, game: str, tag: str, h: Dict[str,str]) -> Optional[str]:
    url = f"https://{routing}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{quote(game)}/{quote(tag)}"
    js = http_json(url, h); return js.get("puuid") if js else None

def match_ids_by_puuid(routing: str, puuid: str, count: int, h: Dict[str,str]) -> List[str]:
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={count}&type=ranked"
    js = http_json(url, h); return js if isinstance(js, list) else []

def match_detail(routing: str, match_id: str, h: Dict[str,str]) -> Optional[Dict[str,Any]]:
    url = f"https://{routing}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    return http_json(url, h)

def summoner_by_id(platform: str, enc_sid: str, h: Dict[str,str]) -> Optional[Dict[str,Any]]:
    url = f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/{enc_sid}"
    return http_json(url, h)

def summoner_by_name(platform: str, name: str, h: Dict[str,str]) -> Optional[Dict[str,Any]]:
    url = f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{quote(name)}"
    return http_json(url, h)

def challenger_entries(platform: str, queue: str, h: Dict[str,Any]) -> List[Dict[str,Any]]:
    url = f"https://{platform}.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/{queue}"
    js = http_json(url, h); return js.get("entries", []) if isinstance(js, dict) else []

def grandmaster_entries(platform: str, queue: str, h: Dict[str,Any]) -> List[Dict[str,Any]]:
    url = f"https://{platform}.api.riotgames.com/lol/league/v4/grandmasterleagues/by-queue/{queue}"
    js = http_json(url, h); return js.get("entries", []) if isinstance(js, dict) else []

def master_entries(platform: str, queue: str, h: Dict[str,Any]) -> List[Dict[str,Any]]:
    url = f"https://{platform}.api.riotgames.com/lol/league/v4/masterleagues/by-queue/{queue}"
    js = http_json(url, h); return js.get("entries", []) if isinstance(js, dict) else []

def league_exp_diamond(platform: str, queue: str, div: str, page: int, h: Dict[str,Any]) -> List[Dict[str,Any]]:
    url = f"https://{platform}.api.riotgames.com/lol/league-exp/v4/entries/{queue}/DIAMOND/{div}?page={page}"
    js = http_json(url, h); return js if isinstance(js, list) else []

# ---------- Parse ----------
def parse_row(match_json: Dict[str,Any], target_puuid: str) -> Optional[Dict[str,Any]]:
    try:
        info = match_json.get("info", {})
        game_id = info.get("gameId") or match_json.get("metadata",{}).get("matchId") or str(uuid4())
        me = None
        for p in info.get("participants", []):
            if p.get("puuid") == target_puuid:
                me = p; break
        if not me:
            log("[parse] 참가자에 puuid 없음"); return None
        return {
            "gameId": game_id,
            "summonerName": me.get("summonerName",""),
            "champion": me.get("championName",""),
            "kills": me.get("kills",0),
            "deaths": me.get("deaths",0),
            "assists": me.get("assists",0),
            "teamPosition": me.get("teamPosition",""),
            "win": me.get("win", False),
            "kda": me.get("challenges",{}).get("kda", 0.0),
            "cs": (me.get("totalMinionsKilled",0) or 0) + (me.get("neutralMinionsKilled",0) or 0),
            "timePlayed": me.get("timePlayed",0)
        }
    except Exception as e:
        log(f"[parse-error] {e}"); return None

# ---------- Collectors ----------
def collect_ids(out_csv: str, riot_ids: List[str], routing: str, count_per_user: int, h: Dict[str,str]):
    w, f = writer(out_csv); seen = seen_match_ids(out_csv); wrote = 0
    try:
        for rid in riot_ids:
            if "#" not in rid: log(f"[ids] 스킵(형식): {rid}"); continue
            name, tag = rid.split("#",1)
            log(f"[ids] {name}#{tag} → puuid 조회")
            puuid = account_by_riot_id(routing, name, tag, h)
            if not puuid: continue
            mids = match_ids_by_puuid(routing, puuid, count_per_user, h)
            log(f"[ids] match ids: {len(mids)}개")
            for mid in mids:
                if str(mid) in seen: continue
                md = match_detail(routing, mid, h)
                if not md: time.sleep(REQUEST_GAP_SEC); continue
                row = parse_row(md, puuid)
                if row and str(row["gameId"]) not in seen:
                    w.writerow(row); wrote += 1; seen.add(str(row["gameId"]))
                time.sleep(REQUEST_GAP_SEC)
    finally:
        f.close()
    log(f"[ids] 완료: 새 행 {wrote}개 → {out_csv}")

def collect_highrank(out_csv: str, platform: str, routing: str,
                     include_dia: bool, dia_pages: int,
                     count_per_user: int, h: Dict[str,str]):
    w, f = writer(out_csv); seen = seen_match_ids(out_csv); wrote = 0
    try:
        # 챌/그마/마스터 — summonerId 사용
        for tier_name, loader in [("CHALLENGER",challenger_entries),
                                  ("GRANDMASTER",grandmaster_entries),
                                  ("MASTER",master_entries)]:
            ents = loader(platform, QUEUE, h)
            log(f"[seed] {tier_name}: {len(ents)}명")
            for e in ents:
                sid = e.get("summonerId")
                if not sid:
                    log("[seed] summonerId 없음"); continue
                s = summoner_by_id(platform, sid, h)
                puuid = s.get("puuid") if s else None
                if not puuid:
                    log("[seed] puuid 없음"); continue
                mids = match_ids_by_puuid(routing, puuid, count_per_user, h)
                for mid in mids:
                    if str(mid) in seen: continue
                    md = match_detail(routing, mid, h)
                    if not md: time.sleep(REQUEST_GAP_SEC); continue
                    row = parse_row(md, puuid)
                    if row and str(row["gameId"]) not in seen:
                        w.writerow(row); wrote += 1; seen.add(str(row["gameId"]))
                    time.sleep(REQUEST_GAP_SEC)

        # 다이아 — summonerName → by-name → puuid
        # 다이아 — league-exp 는 지역/버전에 따라 필드 차이가 있을 수 있음
        if include_dia:
            for div in ["I","II","III","IV"]:
                for page in range(1, dia_pages+1):
                    ents = league_exp_diamond(platform, QUEUE, div, page, h)
                    if not ents:
                        log(f"[diamond] {div} p{page}: 빈 페이지"); break
                    log(f"[diamond] {div} p{page}: {len(ents)}명")

                    # 페이지마다 첫 몇 개의 키를 한 번만 덤프해 구조 확인
                    for i, e in enumerate(ents[:3]):
                        try:
                            log(f"[diamond][peek] keys={list(e.keys())}")
                        except Exception:
                            pass

                    for e in ents:
                        puuid = None

                        # 1) summonerId 가 있는 경우 (가장 빠름)
                        sid = e.get("summonerId")
                        if sid:
                            s = summoner_by_id(platform, sid, h)
                            puuid = s.get("puuid") if s else None

                        # 2) summonerName 으로 보강
                        if not puuid:
                            name = e.get("summonerName")
                            if name:
                                s = summoner_by_name(platform, name, h)
                                puuid = s.get("puuid") if s else None

                        # 3) (일부 응답) 이미 puuid 를 주는 경우 대비
                        if not puuid and isinstance(e.get("puuid"), str):
                            puuid = e["puuid"]

                        if not puuid:
                            # 왜 못찾는지 확인 위해 엔트리 일부 내용을 로그
                            log(f"[diamond] 식별 불가 entry={ {k:e.get(k) for k in list(e.keys())[:6]} }")
                            continue

                        # puuid 확보 후 매치 수집
                        mids = match_ids_by_puuid(routing, puuid, count_per_user, h)
                        for mid in mids:
                            if str(mid) in seen:
                                continue
                            md = match_detail(routing, mid, h)
                            if not md:
                                time.sleep(REQUEST_GAP_SEC); continue
                            row = parse_row(md, puuid)
                            if row and str(row["gameId"]) not in seen:
                                w.writerow(row); wrote += 1; seen.add(str(row["gameId"]))
                            time.sleep(REQUEST_GAP_SEC)

    finally:
        f.close()
    log(f"[highrank] 완료: 새 행 {wrote}개 → {out_csv}")

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="LoL 대량 수집 CLI (v4)")
    ap.add_argument("--api-key", default=None, help="Riot API 키")
    ap.add_argument("--platform", default=DEFAULT_PLATFORM, help="kr/jp1/na1/euw1 …")
    ap.add_argument("--routing",  default=DEFAULT_ROUTING,  help="asia/americas/europe")
    sub = ap.add_subparsers(dest="mode", required=True)

    sp1 = sub.add_parser("ids", help="Riot ID들로 수집 (예: Hide on bush#KR1)")
    sp1.add_argument("--riot-id", action="append", default=[], help="여러 번 지정 가능")
    sp1.add_argument("--riot-id-file", default=None, help="파일 한 줄당 Riot ID 하나")
    sp1.add_argument("--out", default=None, help="출력 CSV (기본: matches_<name>_<tag>.csv)")
    sp1.add_argument("--count-per-user", type=int, default=DEFAULT_CPU, help="유저당 매치 수")

    sp2 = sub.add_parser("highrank", help="챌/그마/마스터(+옵션: 다이아) 대량 수집")
    sp2.add_argument("--out", required=True, help="출력 CSV")
    sp2.add_argument("--include-diamond", action="store_true", help="다이아 포함")
    sp2.add_argument("--diamond-pages", type=int, default=5, help="다이아 division당 페이지 수")
    sp2.add_argument("--count-per-user", type=int, default=DEFAULT_CPU, help="유저당 매치 수")

    sp3 = sub.add_parser("smoketest", help="스모크 테스트(단일 사용자 소량)")
    sp3.add_argument("--riot-id", required=True, help="예: Hide on bush#KR1")
    sp3.add_argument("--out", default="data/reference/smoketest.csv", help="출력 CSV")
    sp3.add_argument("--count-per-user", type=int, default=3, help="소량(3~5 권장)")

    args = ap.parse_args()
    key = ensure_key(args.api_key); h = hdrs(key)

    if args.mode == "ids":
        ids: List[str] = []
        if args.riot_id: ids.extend(args.riot_id)
        if args.riot_id_file and os.path.exists(args.riot_id_file):
            with open(args.riot_id_file, "r", encoding="utf-8") as f:
                ids.extend([ln.strip() for ln in f if ln.strip()])
        if not ids: raise SystemExit("❌ Riot ID가 없습니다. --riot-id 또는 --riot-id-file")
        out = args.out
        if not out and len(ids) == 1 and "#" in ids[0]:
            nm, tg = ids[0].split("#",1); out = os.path.join("data", "users", f"matches_{nm}_{tg}.csv")
        if not out: out = os.path.join("data", "users", "matches_multi_ids.csv")
        collect_ids(out, ids, args.routing, args.count_per_user, h)

    elif args.mode == "highrank":
        collect_highrank(args.out, args.platform, args.routing,
                         args.include_diamond, args.diamond_pages,
                         args.count_per_user, h)

    elif args.mode == "smoketest":
        collect_ids(args.out, [args.riot_id], args.routing, args.count_per_user, h)

if __name__ == "__main__":
    main()
