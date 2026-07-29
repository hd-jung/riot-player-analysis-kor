
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
metrics_cli.py — CLI-only metrics runner for LoL recommendations
- Input: a CSV like highrank.csv with columns:
  gameId, summonerName, champion, kills, deaths, assists, teamPosition, win, kda, cs, timePlayed

What it does:
- Builds a simple baseline recommender per position (TOP/JUNGLE/MID/BOT/SUPPORT) using global stats.
- Two eval modes:
  1) global: uses all data to build top-K lists, then checks hit on every row (fast, optimistic)
  2) loo: leave-one-out per row (rebuilds stats without the target row), with optional sampling (slower, realistic)

Metrics:
- HR@K (Hit Rate@K)
- nDCG@K (binary relevance; reduces to reciprocal rank if hit)
- Optional: MSE if you provide a --predict-prob strategy (pickrate or winrate)

Usage examples:
  python metrics/metrics_cli.py --data data/reference/highrank.csv --mode global --k 10
  python metrics/metrics_cli.py --data data/reference/highrank.csv --mode loo --k 10 --sample 5000
"""

import argparse, csv, math, random, sys
from collections import defaultdict, Counter

import pandas as pd
import numpy as np

POSITIONS = ["TOP","JUNGLE","MIDDLE","BOTTOM","UTILITY","TOP_LANE","MID","JG","BOT","SUP","SUPPORT"]
# Normalize teamPosition to 5 roles
ROLE_MAP = {
    "TOP": "TOP", "TOP_LANE": "TOP",
    "JUNGLE": "JUNGLE", "JG": "JUNGLE",
    "MIDDLE": "MID", "MID": "MID",
    "BOTTOM": "BOT", "BOT": "BOT",
    "UTILITY": "SUP", "SUP": "SUP", "SUPPORT": "SUP"
}

def norm_role(x: str) -> str:
    if not isinstance(x, str): return "UNK"
    x = x.strip().upper()
    return ROLE_MAP.get(x, x if x in ["TOP","JUNGLE","MID","BOT","SUP"] else "UNK")

def load_df(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Basic cleaning
    if "teamPosition" in df.columns:
        df["role"] = df["teamPosition"].apply(norm_role)
    else:
        df["role"] = "UNK"
    if "win" in df.columns and df["win"].dtype != bool:
        # Map 'True'/'False'/1/0
        df["win"] = df["win"].astype(str).str.lower().isin(["true","1","t","y","yes"])
    return df

def build_stats(df: pd.DataFrame, min_games: int = 10):
    """Return dict: role -> {champ: {games, wins}}"""
    stats = defaultdict(lambda: {"games": Counter(), "wins": Counter()})
    for _, r in df.iterrows():
        role = r.get("role", "UNK")
        champ = r.get("champion", None)
        if not isinstance(champ, str) or role == "UNK":
            continue
        stats[role]["games"][champ] += 1
        if bool(r.get("win", False)):
            stats[role]["wins"][champ] += 1
    # compute winrate and pickrate
    tables = {}
    for role, dic in stats.items():
        rows = []
        for champ, g in dic["games"].items():
            w = dic["wins"][champ]
            if g < 1: continue
            rows.append((champ, g, w, (w / g)))
        if rows:
            t = pd.DataFrame(rows, columns=["champion","games","wins","winrate"])
            t = t.sort_values(["winrate","games"], ascending=[False, False]).reset_index(drop=True)
            tables[role] = t
    return tables

def topk_by_winrate(table: pd.DataFrame, k: int, min_games: int = 10):
    if table is None or table.empty: return []
    t = table[table["games"] >= min_games]
    if t.empty:
        t = table  # fallback
    return list(t.head(k)["champion"].astype(str))

def rank_of(champ: str, recs: list) -> int:
    try:
        return recs.index(champ) + 1
    except ValueError:
        return -1

def eval_global(df: pd.DataFrame, k: int, min_games: int):
    tables = build_stats(df, min_games=min_games)
    hits = 0
    dcg_sum = 0.0
    total = 0
    per_role = defaultdict(lambda: {"hits":0, "n":0})
    for _, r in df.iterrows():
        role = r.get("role", "UNK")
        champ = r.get("champion", None)
        if role not in tables or not isinstance(champ, str):
            continue
        recs = topk_by_winrate(tables[role], k, min_games)
        if not recs:
            continue
        total += 1
        rk = rank_of(champ, recs)
        if rk != -1:
            hits += 1
            dcg_sum += 1.0 / math.log2(rk + 1)
            per_role[role]["hits"] += 1
        per_role[role]["n"] += 1
    hr = hits / total if total else 0.0
    ndcg = (dcg_sum / total) if total else 0.0  # IDCG = 1 for binary relevance
    return hr, ndcg, total, per_role

def eval_loo(df: pd.DataFrame, k: int, min_games: int, sample: int = None, seed: int = 42):
    idxs = list(df.index)
    if sample is not None and sample < len(idxs):
        random.Random(seed).shuffle(idxs)
        idxs = idxs[:sample]
    hits = 0
    dcg_sum = 0.0
    total = 0
    per_role = defaultdict(lambda: {"hits":0, "n":0})
    for i in idxs:
        r = df.loc[i]
        role = r.get("role", "UNK")
        champ = r.get("champion", None)
        if not isinstance(champ, str) or role == "UNK":
            continue
        # build stats without this row
        df2 = df.drop(index=i)
        tables = build_stats(df2, min_games=min_games)
        if role not in tables:
            continue
        recs = topk_by_winrate(tables[role], k, min_games)
        if not recs:
            continue
        total += 1
        rk = rank_of(champ, recs)
        if rk != -1:
            hits += 1
            dcg_sum += 1.0 / math.log2(rk + 1)
            per_role[role]["hits"] += 1
        per_role[role]["n"] += 1
    hr = hits / total if total else 0.0
    ndcg = (dcg_sum / total) if total else 0.0
    return hr, ndcg, total, per_role

def main():
    ap = argparse.ArgumentParser(description="CLI metrics for LoL recommendations")
    ap.add_argument("--data", required=True, help="CSV path (e.g., data/highrank.csv)")
    ap.add_argument("--mode", choices=["global","loo"], default="global", help="global=fast, loo=leave-one-out")
    ap.add_argument("--k", type=int, default=10, help="Top-K")
    ap.add_argument("--min-games", type=int, default=10, help="Minimum games per champion to be eligible")
    ap.add_argument("--sample", type=int, default=None, help="Only for loo: number of rows to evaluate")
    args = ap.parse_args()

    df = load_df(args.data)
    if len(df) == 0:
        print("No rows in data.", file=sys.stderr)
        sys.exit(1)

    if args.mode == "global":
        hr, ndcg, n, per_role = eval_global(df, args.k, args.min_games)
    else:
        hr, ndcg, n, per_role = eval_loo(df, args.k, args.min_games, sample=args.sample)

    print("=== Metrics ===")
    print(f"Mode         : {args.mode}")
    print(f"Rows eval    : {n}")
    print(f"HR@{args.k}     : {hr:.4f}")
    print(f"nDCG@{args.k}   : {ndcg:.4f}")
    if per_role:
        print("\nPer-role HR:")
        for role, d in per_role.items():
            if d["n"] > 0:
                print(f"  {role:>3}: {d['hits']}/{d['n']} = {d['hits']/d['n']:.4f}")

if __name__ == "__main__":
    main()
