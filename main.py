from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.analytics import analyze_matches, benchmark_context
from app.config import PUBLIC_DIR, REFERENCE_DATA_DIR, TEMPLATES_DIR, riot_api_key
from app.riot import RiotAPIError, RiotClient, read_cache, split_riot_id


app = FastAPI(
    title="Rift Signal 한국어판",
    description="최상위 티어 기준과 비교해 개인 맞춤형 리그 오브 레전드 훈련 루틴을 제공하는 서비스입니다.",
    version="1.3.1",
)

# Vercel serves files under public/ from its CDN. These mounts keep local
# uvicorn development working and remain safe if a deployment bundle omits
# static directories.
if (PUBLIC_DIR / "css").is_dir():
    app.mount("/css", StaticFiles(directory=PUBLIC_DIR / "css"), name="css")
if (PUBLIC_DIR / "js").is_dir():
    app.mount("/js", StaticFiles(directory=PUBLIC_DIR / "js"), name="js")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/favicon.svg", include_in_schema=False)
async def favicon():
    return FileResponse(PUBLIC_DIR / "favicon.svg", media_type="image/svg+xml")


class AnalyzeRequest(BaseModel):
    riot_id: str = Field(min_length=3, max_length=40)
    match_count: int = Field(default=10, ge=3, le=20)
    refresh: bool = False


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"page": "home"},
    )


@app.get("/analysis", response_class=HTMLResponse)
async def analysis_page(
    request: Request,
    riot_id: str = Query(default="Hide on bush#KR1"),
    count: int = Query(default=10, ge=3, le=20),
):
    return templates.TemplateResponse(
        request=request,
        name="analysis.html",
        context={"page": "analysis", "riot_id": riot_id, "count": count},
    )


@app.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request):
    data_path = REFERENCE_DATA_DIR / "highrank.csv"
    benchmark = benchmark_context(str(data_path))
    return templates.TemplateResponse(
        request=request,
        name="metrics.html",
        context={"page": "metrics", "benchmark": benchmark},
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": app.version,
        "riot_api_configured": bool(riot_api_key()),
    }


@app.post("/api/analyze")
async def analyze(payload: AnalyzeRequest):
    try:
        game_name, tag_line = split_riot_id(payload.riot_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    rows = []
    source = "cache"
    if not payload.refresh:
        rows = read_cache(game_name, tag_line)

    if not rows:
        key = riot_api_key()
        if not key:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Riot API 키가 설정되지 않았고 이 Riot ID의 저장된 경기 데이터도 "
                    "없습니다."
                ),
            )
        try:
            rows = await RiotClient(key).collect(payload.riot_id, payload.match_count)
            source = "live"
        except RiotAPIError as exc:
            cached = read_cache(game_name, tag_line)
            if cached:
                rows = cached
                source = "cache-fallback"
            else:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        result = analyze_matches(rows[: payload.match_count], payload.riot_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["source"] = source
    return result
