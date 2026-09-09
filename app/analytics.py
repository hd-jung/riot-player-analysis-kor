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

    summary = {
        "games": total,
        "wins": wins,
        "losses": total - wins,
        "win_rate": round(wins / total * 100, 1),
        "avg_kda": round(float(frame["kda"].mean()), 2),
        "avg_cs": round(float(frame["cs"].mean()), 1),
        "avg_cs_min": round(float(frame["cs_per_min"].mean()), 1),
        "avg_deaths": round(float(frame["deaths"].mean()), 1),
        "favorite_role": favorite_role,
        "champion_pool": int(frame["champion"].nunique()),
    }
    benchmark = _player_benchmark(frame, favorite_role)
    training_plan = _training_plan(summary, benchmark, recommendations)

    return {
        "riot_id": riot_id,
        "summary": summary,
        "champions": champions,
        "roles": roles,
        "recommendations": recommendations,
        "recent_matches": recent,
        "benchmark": benchmark,
        "training_plan": training_plan,
    }


def _player_benchmark(frame: pd.DataFrame, favorite_role: str) -> dict[str, Any]:
    """사용자의 주 포지션과 KR 최상위 티어 경기 중앙값을 비교합니다."""
    from .config import REFERENCE_DATA_DIR

    reference = _records_frame(
        pd.read_csv(REFERENCE_DATA_DIR / "highrank.csv").to_dict("records")
    )
    role_reference = reference[reference["role"] == favorite_role]
    if role_reference.empty:
        role_reference = reference

    targets = {
        "win_rate": round(float(role_reference["win"].mean()) * 100, 1),
        "avg_kda": round(float(role_reference["kda"].median()), 2),
        "avg_cs_min": round(float(role_reference["cs_per_min"].median()), 1),
        "avg_deaths": round(float(role_reference["deaths"].median()), 1),
    }
    actual = {
        "win_rate": round(float(frame["win"].mean()) * 100, 1),
        "avg_kda": round(float(frame["kda"].mean()), 2),
        "avg_cs_min": round(float(frame["cs_per_min"].mean()), 1),
        "avg_deaths": round(float(frame["deaths"].mean()), 1),
    }
    labels = {
        "win_rate": ("승률", "%", True),
        "avg_kda": ("평균 KDA", "", True),
        "avg_cs_min": ("분당 CS", "", True),
        "avg_deaths": ("경기당 데스", "", False),
    }
    comparisons = []
    for key, (label, unit, higher_is_better) in labels.items():
        player_value = actual[key]
        target_value = targets[key]
        raw_gap = (target_value - player_value) if higher_is_better else (player_value - target_value)
        scale = max(abs(target_value), 1)
        comparisons.append(
            {
                "key": key,
                "label": label,
                "unit": unit,
                "player": player_value,
                "target": target_value,
                "gap": round(raw_gap, 2),
                "gap_score": round(raw_gap / scale * 100, 1),
                "status": "focus" if raw_gap > scale * 0.08 else "on-track",
            }
        )
    return {
        "cohort": f"KR 최상위 티어 {favorite_role}",
        "sample_games": int(len(role_reference)),
        "confidence": "높음" if len(frame) >= 15 else "보통" if len(frame) >= 8 else "초기",
        "comparisons": comparisons,
        "disclaimer": "KR 챌린저·그랜드마스터·마스터 랭크 경기로 만든 방향성 기준이며 프로 선수 데이터는 아닙니다.",
    }


def _training_plan(
    summary: dict[str, Any],
    benchmark: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    comparison = {item["key"]: item for item in benchmark["comparisons"]}
    focus = sorted(
        benchmark["comparisons"], key=lambda item: item["gap_score"], reverse=True
    )
    drills = {
        "avg_cs_min": {
            "title": "CS 안정성",
            "goal": f"두 경기에서 분당 CS {max(comparison['avg_cs_min']['target'], comparison['avg_cs_min']['player'])} 달성",
            "session": "10분 막타 연습 후 랭크 1경기에서 5분·10분 CS를 기록합니다.",
        },
        "avg_deaths": {
            "title": "생존 습관",
            "goal": f"경기당 데스 {min(comparison['avg_deaths']['target'], comparison['avg_deaths']['player'])} 이하 유지",
            "session": "패배 2경기의 첫 데스를 복기하고 각각 예방 원인과 더 안전한 선택을 하나씩 적습니다.",
        },
        "avg_kda": {
            "title": "교전 선택",
            "goal": f"연습 세션 평균 KDA {max(comparison['avg_kda']['target'], comparison['avg_kda']['player'])} 달성",
            "session": "교전 전 아군 수·핵심 스킬·퇴로를 확인하고, 종료 후 가치가 낮았던 교전 2개를 복기합니다.",
        },
        "win_rate": {
            "title": "승리 전환 루틴",
            "goal": f"연습 구간 승률 {max(comparison['win_rate']['target'], comparison['win_rate']['player'])}% 이상 유지",
            "session": "귀환할 때마다 다음 목표물을 정하고 이후 90초를 그 목표물 중심으로 플레이합니다.",
        },
    }
    selected = [item for item in focus if item["gap_score"] > 0][:3]
    if len(selected) < 3:
        selected = (selected + [item for item in focus if item not in selected])[:3]
    primary_pick = recommendations[0]["champion"] if recommendations else "주력 챔피언"
    schedule = []
    for index in range(7):
        if index == 0:
            task = "기준 경기 복기"
            detail = f"최근 3경기의 첫 실수를 하나씩 기록하고 {primary_pick}을 이번 주 주력 연습 챔피언으로 정합니다."
        elif index in {1, 3, 5}:
            drill = drills[selected[(index // 2) % len(selected)]["key"]]
            task, detail = drill["title"], drill["session"]
        elif index in {2, 4}:
            task = "집중 랭크 블록"
            detail = f"{primary_pick}으로 랭크 2경기를 플레이하고 오늘의 목표 한 가지만 기록한 뒤 종료합니다."
        else:
            task = "재측정 및 조정"
            detail = "최신 경기를 다시 분석하고 1일 차와 네 가지 최상위 티어 격차를 비교합니다."
        schedule.append({"day": index + 1, "label": f"{index + 1}일 차", "task": task, "detail": detail})
    return {
        "title": "7일 실력 향상 루틴",
        "primary_role": summary["favorite_role"],
        "primary_pick": primary_pick,
        "focus_areas": [
            {
                "key": item["key"],
                "title": drills[item["key"]]["title"],
                "goal": drills[item["key"]]["goal"],
                "priority": index + 1,
            }
            for index, item in enumerate(selected)
        ],
        "schedule": schedule,
        "completion_storage": "browser",
        "retest_after_days": 7,
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
