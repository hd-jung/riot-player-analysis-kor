from typing import Any


DEMO_RIOT_ID = "dummy_player#KR1"


def is_demo_riot_id(riot_id: str) -> bool:
    return riot_id.strip().lower() == DEMO_RIOT_ID.lower()


def demo_match_rows() -> list[dict[str, Any]]:
    games = [
        ("Ahri", 9, 3, 10, True, 248, 1900),
        ("Orianna", 6, 4, 12, True, 232, 1840),
        ("Ahri", 7, 2, 11, True, 261, 1960),
        ("Syndra", 8, 5, 8, False, 239, 1880),
        ("Ahri", 5, 3, 14, True, 244, 1810),
        ("Orianna", 4, 5, 9, False, 218, 1770),
        ("Ahri", 10, 4, 7, True, 272, 2010),
        ("Syndra", 6, 6, 10, False, 225, 1860),
        ("Ahri", 8, 3, 13, True, 257, 1930),
        ("Orianna", 3, 6, 8, False, 209, 1740),
        ("Ahri", 7, 4, 9, True, 246, 1880),
        ("Viktor", 5, 5, 11, False, 238, 1920),
        ("Orianna", 6, 3, 15, True, 251, 1970),
        ("Ahri", 9, 5, 8, True, 263, 2040),
        ("Syndra", 4, 4, 12, False, 226, 1790),
        ("Ahri", 8, 2, 10, True, 254, 1870),
        ("Viktor", 6, 6, 9, False, 241, 1990),
        ("Orianna", 5, 3, 13, True, 237, 1830),
        ("Ahri", 11, 4, 9, True, 269, 2020),
        ("Syndra", 5, 5, 10, False, 229, 1850),
    ]
    rows = []
    for index, (champion, kills, deaths, assists, win, cs, duration) in enumerate(games):
        rows.append(
            {
                "gameId": f"DEMO_{2000 - index}",
                "summonerName": DEMO_RIOT_ID,
                "champion": champion,
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "teamPosition": "MIDDLE",
                "win": win,
                "kda": round((kills + assists) / max(deaths, 1), 3),
                "cs": cs,
                "timePlayed": duration,
            }
        )
    return rows

