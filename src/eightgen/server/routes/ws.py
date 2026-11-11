"""WebSocket live streaming routes."""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from eightgen.config.loader import get_settings
from eightgen.core.agent import Agent

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/generate")
async def websocket_generate(websocket: WebSocket):
    """Stream LLM tokens during game generation over WebSocket."""
    await websocket.accept()
    settings = get_settings()
    agent = Agent(settings)

    try:
        raw_msg = await websocket.receive_text()
        data = json.loads(raw_msg)
        prompt = data.get("prompt", "").strip()
        category = data.get("category")
        override_model = data.get("model")
        instant = data.get("instant", False)
        game_reference = data.get("game_reference")

        if not prompt and not game_reference:
            await websocket.send_json({"type": "error", "message": "Prompt or game_reference is required."})
            await websocket.close()
            return

        if override_model:
            agent.provider.model = override_model

        async def _stream_delta(chunk: str):
            try:
                await websocket.send_json({"type": "delta", "chunk": chunk})
            except Exception:
                pass

        # Notify started
        await websocket.send_json({"type": "start", "prompt": prompt or game_reference})

        game = await agent.create_game(
            prompt=prompt,
            category=category,
            stream_callback=_stream_delta,
            auto_open=False,
            instant=instant,
            game_reference=game_reference,
        )

        await websocket.send_json({
            "type": "completed",
            "game": game.model_dump(mode="json"),
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
