import asyncio
import csv
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from .config import USER_DATA_DIR


COLUMNS = [
    "gameId",
    "summonerName",
    "champion",
    "kills",
    "deaths",
    "assists",
    "teamPosition",
    "win",
    "kda",
    "cs",
    "timePlayed",
]


class RiotAPIError(RuntimeError):
    """사용자에게 표시할 Riot API 오류."""


def split_riot_id(riot_id: str) -> tuple[str, str]:
    if "#" not in riot_id:
        raise ValueError("Riot ID를 게임이름#태그 형식으로 입력하세요.")
    game_name, tag_line = (part.strip() for part in riot_id.split("#", 1))
    if not game_name or not tag_line:
        raise ValueError("게임 이름과 태그를 모두 입력하세요.")
    return game_name, tag_line


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "", value).strip()
    return cleaned or "unknown"


def cache_path(game_name: str, tag_line: str) -> Path:
    return USER_DATA_DIR / (
        f"matches_{_safe_filename_part(game_name)}_{_safe_filename_part(tag_line)}.csv"
    )


def read_cache(game_name: str, tag_line: str) -> list[dict[str, Any]]:
    filename = cache_path(game_name, tag_line).name
    candidates = [
        USER_DATA_DIR / filename,
        Path(tempfile.gettempdir()) / "rift-signal" / filename,
    ]
    for path in candidates:
        if path.exists():
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return list(csv.DictReader(handle))
    return []


def write_cache(game_name: str, tag_line: str, rows: list[dict[str, Any]]) -> Path:
    filename = cache_path(game_name, tag_line).name
    candidates = [
        USER_DATA_DIR / filename,
        Path(tempfile.gettempdir()) / "rift-signal" / filename,
    ]
    last_error: OSError | None = None
    for path in candidates:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
            return path
        except OSError as exc:
            last_error = exc
    raise RiotAPIError(f"경기 결과를 캐시에 저장하지 못했습니다: {last_error}")


class RiotClient:
    def __init__(self, api_key: str, routing: str = "asia") -> None:
        if not api_key:
            raise RiotAPIError("RIOT_API_KEY가 설정되지 않았습니다.")
        self.routing = routing
        self.headers = {"X-Riot-Token": api_key}
        self.timeout = httpx.Timeout(15.0, connect=10.0)

    async def _get_json(self, client: httpx.AsyncClient, url: str) -> Any:
        for attempt in range(3):
            try:
                response = await client.get(url, headers=self.headers)
            except httpx.RequestError as exc:
                if attempt == 2:
                    raise RiotAPIError(f"Riot Games 서버에 연결하지 못했습니다: {exc}") from exc
                await asyncio.sleep(0.6 * (attempt + 1))
                continue

            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                wait = float(response.headers.get("Retry-After", "1") or "1")
                await asyncio.sleep(min(wait, 5.0))
                continue
            if response.status_code in {401, 403}:
                raise RiotAPIError("Riot API 키가 잘못되었거나 만료되었습니다.")
            if response.status_code == 404:
                raise RiotAPIError("Riot ID 또는 경기 데이터를 찾지 못했습니다.")
            if response.status_code >= 500 and attempt < 2:
                await asyncio.sleep(0.8 * (attempt + 1))
                continue
            raise RiotAPIError(
                f"Riot Games에서 HTTP {response.status_code} 오류를 반환했습니다."
            )

        raise RiotAPIError("여러 차례 시도했지만 Riot Games에서 응답하지 않았습니다.")

    async def collect(self, riot_id: str, count: int) -> list[dict[str, Any]]:
        game_name, tag_line = split_riot_id(riot_id)
        encoded_game = quote(game_name, safe="")
        encoded_tag = quote(tag_line, safe="")
        base = f"https://{self.routing}.api.riotgames.com"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            account = await self._get_json(
                client,
                f"{base}/riot/account/v1/accounts/by-riot-id/{encoded_game}/{encoded_tag}",
            )
            puuid = account.get("puuid")
            if not puuid:
                raise RiotAPIError("Riot 계정 응답에 PUUID가 포함되지 않았습니다.")

            match_ids = await self._get_json(
                client,
                f"{base}/lol/match/v5/matches/by-puuid/{puuid}/ids"
                f"?start=0&count={count}&type=ranked",
            )

            rows: list[dict[str, Any]] = []
            for match_id in match_ids:
                match = await self._get_json(
                    client, f"{base}/lol/match/v5/matches/{match_id}"
                )
                row = self._parse_match(match, puuid, riot_id)
                if row:
                    rows.append(row)
                await asyncio.sleep(0.12)

        if not rows:
            raise RiotAPIError("이 Riot ID에서 분석할 랭크 경기를 찾지 못했습니다.")
        write_cache(game_name, tag_line, rows)
        return rows

    @staticmethod
    def _parse_match(
        match: dict[str, Any], puuid: str, riot_id: str
    ) -> dict[str, Any] | None:
        info = match.get("info", {})
        participant = next(
            (item for item in info.get("participants", []) if item.get("puuid") == puuid),
            None,
        )
        if not participant:
            return None

        deaths = int(participant.get("deaths", 0) or 0)
        kills = int(participant.get("kills", 0) or 0)
        assists = int(participant.get("assists", 0) or 0)
        kda = participant.get("challenges", {}).get("kda")
        if kda is None:
            kda = (kills + assists) / max(deaths, 1)

        return {
            "gameId": info.get("gameId")
            or match.get("metadata", {}).get("matchId", ""),
            "summonerName": riot_id,
            "champion": participant.get("championName", "알 수 없음"),
            "kills": kills,
            "deaths": deaths,
            "assists": assists,
            "teamPosition": participant.get("teamPosition", "알 수 없음"),
            "win": bool(participant.get("win", False)),
            "kda": round(float(kda), 3),
            "cs": int(participant.get("totalMinionsKilled", 0) or 0)
            + int(participant.get("neutralMinionsKilled", 0) or 0),
            "timePlayed": int(participant.get("timePlayed", 0) or 0),
        }
