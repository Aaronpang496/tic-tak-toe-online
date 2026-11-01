# server.py
import asyncio, json, uuid
import websockets
from game_logic import (
    new_game, join, leave, apply_move, apply_ai_move,
    start_ai_game, AI_ID,
)

STATE = new_game()
CLIENTS = {}
NAMES = {}
AI_TASK = None
MODE = "auto"

async def broadcast():
    online = [
        {"id": pid, "name": NAMES.get(pid, "?")}
        for pid in STATE["players"]
    ]
    payload = json.dumps({
        "type": "state",
        "state": STATE,
        "online": online,
        "waiting": len(STATE["players"]) == 1 and not STATE["vs_ai"],
    })
    await asyncio.gather(*(ws.send(payload) for ws in CLIENTS), return_exceptions=True)

async def maybe_start_ai():
    global AI_TASK, STATE
    try:
        await asyncio.sleep(3)
        humans = list(STATE["players"])
        if len(humans) == 1 and not STATE["vs_ai"] and STATE["winner"] is None:
            STATE = start_ai_game(STATE, humans[0], "hard")
            await broadcast()
    except asyncio.CancelledError:
        pass
    finally:
        AI_TASK = None

async def handler(ws):
    global AI_TASK, STATE, MODE
    player_id = str(uuid.uuid4())[:8]
    CLIENTS[ws] = player_id

    if STATE["vs_ai"] and len(STATE["players"]) == 1:
        AI_TASK and AI_TASK.cancel()
        AI_TASK = None
        fresh = new_game()
        for pid in STATE["players"]:
            fresh["names"][pid] = STATE["names"].get(pid, pid)
        fresh["players"] = list(STATE["players"])
        join(fresh, player_id)
        STATE = fresh
    else:
        join(STATE, player_id)
        NAMES[player_id] = STATE["names"].get(player_id, "?")

        if len(STATE["players"]) == 1 and not STATE["vs_ai"] and MODE == "auto":
            AI_TASK and AI_TASK.cancel()
            AI_TASK = asyncio.create_task(maybe_start_ai())

    await ws.send(json.dumps({
        "type": "welcome",
        "player_id": player_id,
        "name": STATE["names"].get(player_id, "?"),
    }))
    await broadcast()

    try:
        async for raw in ws:
            msg = json.loads(raw)

            if msg["type"] == "move":
                STATE = apply_move(STATE, player_id, msg["row"], msg["col"])
                await broadcast()
                if STATE["vs_ai"] and STATE["turn"] == STATE["ai_symbol"] and not STATE["winner"]:
                    await asyncio.sleep(0.6)
                    STATE = apply_ai_move(STATE)
                    await broadcast()

            elif msg["type"] == "reset":
                fresh = new_game()
                for pid in list(CLIENTS.values()):
                    join(fresh, pid, STATE["names"].get(pid))
                if len(CLIENTS) == 1:
                    fresh = start_ai_game(fresh, next(iter(CLIENTS.values())),
                                          STATE.get("ai_difficulty", "hard"))
                STATE = fresh
                AI_TASK and AI_TASK.cancel()
                if len(CLIENTS) == 1 and MODE == "auto":
                    AI_TASK = asyncio.create_task(maybe_start_ai())
                await broadcast()

            elif msg["type"] == "play_ai":
                # Player clicked "Play AI now" (from landing or waiting screen)
                AI_TASK and AI_TASK.cancel()
                AI_TASK = None
                difficulty = msg.get("difficulty", "hard")
                if player_id not in STATE["players"]:
                    join(STATE, player_id)
                    NAMES[player_id] = STATE["names"].get(player_id, "?")
                STATE = start_ai_game(STATE, player_id, difficulty)
                await broadcast()

            elif msg["type"] == "set_mode":
                MODE = msg.get("mode", "auto")
                if MODE == "ai_now":
                    AI_TASK and AI_TASK.cancel()
                    AI_TASK = None
                    difficulty = msg.get("difficulty", "hard")
                    if player_id in STATE["players"]:
                        STATE = start_ai_game(STATE, player_id, difficulty)
                        await broadcast()

            elif msg["type"] == "exit":
                CLIENTS.pop(ws, None)
                STATE = leave(STATE, player_id)
                if len(STATE["players"]) == 1 and not STATE["vs_ai"] and MODE == "auto":
                    AI_TASK and AI_TASK.cancel()
                    AI_TASK = asyncio.create_task(maybe_start_ai())
                elif len(STATE["players"]) == 0:
                    STATE = new_game()
                await broadcast()
                await ws.close()
                return

    finally:
        if ws in CLIENTS:
            CLIENTS.pop(ws, None)
            STATE = leave(STATE, player_id)
            if len(STATE["players"]) == 0:
                STATE = new_game()
                AI_TASK and AI_TASK.cancel()
                AI_TASK = None
            await broadcast()

async def main():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("WS server on ws://0.0.0.0:8765")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
