import os
import json
import asyncio
import functools
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from strategy_builder import (
    parse_strategy_with_ai,
    fetch_and_calculate,
    run_backtest,
    generate_equity_chart,
    WATCHLIST,
)

app = FastAPI(title="QuantFlow Strategy Builder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"


class StrategyRequest(BaseModel):
    strategy: str


@app.post("/api/strategy/stream")
async def stream_strategy(request: StrategyRequest):
    async def generate():
        loop = asyncio.get_event_loop()

        yield f"data: {json.dumps({'type': 'status', 'message': 'Converting your strategy to executable rules...'})}\n\n"
        await asyncio.sleep(0)

        try:
            rules = await loop.run_in_executor(None, parse_strategy_with_ai, request.strategy)
            yield f"data: {json.dumps({'type': 'rules', 'rules': rules})}\n\n"
            await asyncio.sleep(0)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Strategy parsing failed: {e}'})}\n\n"
            return

        all_results = []
        for i, ticker in enumerate(WATCHLIST):
            yield f"data: {json.dumps({'type': 'progress', 'ticker': ticker, 'current': i + 1, 'total': len(WATCHLIST)})}\n\n"
            await asyncio.sleep(0)

            df = await loop.run_in_executor(None, fetch_and_calculate, ticker)
            if df is None:
                result = {"ticker": ticker, "trades": [], "stats": None}
            else:
                result = await loop.run_in_executor(
                    None, functools.partial(run_backtest, df, rules, ticker)
                )

            all_results.append(result)
            yield f"data: {json.dumps({'type': 'ticker_done', 'ticker': ticker, 'stats': result.get('stats'), 'trade_count': len(result.get('trades', []))})}\n\n"
            await asyncio.sleep(0)

        yield f"data: {json.dumps({'type': 'status', 'message': 'Generating equity curve...'})}\n\n"
        await asyncio.sleep(0)

        chart_b64 = await loop.run_in_executor(None, generate_equity_chart, all_results)

        yield f"data: {json.dumps({'type': 'complete', 'chart': chart_b64, 'all_results': all_results})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# Serve React build — must come AFTER API routes
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
