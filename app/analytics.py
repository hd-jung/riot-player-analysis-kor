from typing import Any

import pandas as pd


ROLE_LABELS = {
    "TOP": "탑",
    "JUNGLE": "정글",
    "MIDDLE": "미드",
    "MID": "미드",
    "BOTTOM": "바텀",
    "BOT": "바텀",
    "UTILITY": "서포터",
    "SUPPORT": "서포터",
}


def _bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "t", "yes", "y"})


def _records_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for column in ("kills", "deaths", "assists", "kda", "cs", "timePlayed"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame["win"] = _bool_series(frame["win"])
    frame["champion"] = frame["champion"].fillna("알 수 없음").astype(str)
    frame["role"] = (
        frame["teamPosition"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
        .map(ROLE_LABELS)
        .fillna("유동")
    )
    frame["cs_per_min"] = frame["cs"] / (frame["timePlayed"].clip(lower=1) / 60)
    return frame


def analyze_matches(rows: list[dict[str, Any]], riot_id: str) -> dict[str, Any]:
    frame = _records_frame(rows)
    if frame.empty:
        raise ValueError("분석할 수 있는 경기 데이터가 없습니다.")

    wins = int(frame["win"].sum())
    total = len(frame)
    favorite_role = frame["role"].mode().iloc[0] if not frame["role"].mode().empty else "유동"

    champion_stats = (
        frame.groupby("champion", as_index=False)
        .agg(
            games=("champion", "size"),
            wins=("win", "sum"),
            win_rate=("win", "mean"),
            avg_kda=("kda", "mean"),
            avg_cs=("cs", "mean"),
        )
        .sort_values(["games", "win_rate", "avg_kda"], ascending=[False, False, False])
    )

    champions = [
        {
            "champion": row.champion,
            "games": int(row.games),
            "wins": int(row.wins),
            "win_rate": round(float(row.win_rate) * 100, 1),
            "avg_kda": round(float(row.avg_kda), 2),
            "avg_cs": round(float(row.avg_cs), 1),
        }
        for row in champion_stats.itertuples(index=False)
    ]

    role_stats = (
        frame.groupby("role", as_index=False)
        .agg(games=("role", "size"), win_rate=("win", "mean"), avg_kda=("kda", "mean"))
        .sort_values("games", ascending=False)
    )
    roles = [
        {
            "role": row.role,
            "games": int(row.games),
            "share": round(int(row.games) / total * 100, 1),
            "win_rate": round(float(row.win_rate) * 100, 1),
            "avg_kda": round(float(row.avg_kda), 2),
        }
        for row in role_stats.itertuples(index=False)
    ]

    recent = []
    for row in frame.head(10).itertuples(index=False):
        recent.append(
            {
                "champion": row.champion,
                "role": row.role,
                "win": bool(row.win),
                "score": f"{int(row.kills)} / {int(row.deaths)} / {int(row.assists)}",
                "kda": round(float(row.kda), 2),
                "cs": int(row.cs),
                "duration": round(float(row.timePlayed) / 60),
            }
        )

    recommendations = []
    for item in sorted(
        champions,
        key=lambda value: (value["win_rate"], value["avg_kda"], value["games"]),
        reverse=True,
    )[:3]:
        recommendations.append(
            {
                **item,
                "signal": (
                    "강력 추천 픽"
                    if item["win_rate"] >= 60
                    else "주력 픽 신호"
                    if item["avg_kda"] >= 3
                    else "표본 추가 필요"
                ),
            }
        )

    return {
        "riot_id": riot_id,
        "summary": {
            "games": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total * 100, 1),
            "avg_kda": round(float(frame["kda"].mean()), 2),
            "avg_cs": round(float(frame["cs"].mean()), 1),
            "avg_cs_min": round(float(frame["cs_per_min"].mean()), 1),
            "favorite_role": favorite_role,
            "champion_pool": int(frame["champion"].nunique()),
        },
        "champions": champions,
        "roles": roles,
        "recommendations": recommendations,
        "recent_matches": recent,
    }


def benchmark_context(path: str) -> dict[str, Any]:
    frame = pd.read_csv(path)
    frame["win"] = _bool_series(frame["win"])
    frame["role"] = (
        frame["teamPosition"].fillna("UNKNOWN").astype(str).str.upper().map(ROLE_LABELS)
    )
    frame = frame.dropna(subset=["role", "champion"])

    role_rows = []
    hits = 0
    dcg = 0.0
    evaluated = 0
    top_picks: dict[str, list[dict[str, Any]]] = {}

    for role, group in frame.groupby("role"):
        table = (
            group.groupby("champion", as_index=False)
            .agg(games=("champion", "size"), win_rate=("win", "mean"))
            .sort_values(["win_rate", "games"], ascending=[False, False])
        )
        eligible = table[table["games"] >= 10]
        if eligible.empty:
            eligible = table
        top = eligible.head(10).reset_index(drop=True)
        recs = top["champion"].tolist()
        role_hits = 0
        role_dcg = 0.0
        for champion in group["champion"]:
            evaluated += 1
            if champion in recs:
                rank = recs.index(champion) + 1
                role_hits += 1
                hits += 1
                gain = 1.0 / __import__("math").log2(rank + 1)
                role_dcg += gain
                dcg += gain
        role_rows.append(
            {
                "role": role,
                "games": len(group),
                "hit_rate": round(role_hits / len(group) * 100, 1),
                "signal": "우수" if role_hits / len(group) >= 0.3 else "개선 중",
            }
        )
        top_picks[role] = [
            {
                "champion": item.champion,
                "games": int(item.games),
                "win_rate": round(float(item.win_rate) * 100, 1),
            }
            for item in top.head(5).itertuples(index=False)
        ]

    return {
        "rows": len(frame),
        "matches": int(frame["gameId"].nunique()),
        "champions": int(frame["champion"].nunique()),
        "hr10": round(hits / evaluated * 100, 1) if evaluated else 0,
        "ndcg10": round(dcg / evaluated * 100, 1) if evaluated else 0,
        "roles": sorted(role_rows, key=lambda row: row["hit_rate"], reverse=True),
        "top_picks": top_picks,
    }
