
import argparse
import asyncio
import json
import random
import websockets
import requests

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8000")
    ap.add_argument("--game_id", required=True)
    ap.add_argument("--api_key", required=False, default=None)
    args = ap.parse_args()

    ws_url = args.server.replace("http", "ws") + f"/ws/game/{args.game_id}"

    async def run():
        async with websockets.connect(ws_url) as ws:
            print(f"Connected to {ws_url}")
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                print("Event:", data)
                if data.get("type") == "session_started":
                    session_id = data["session_id"]
                    # Simulate game runtime
                    await asyncio.sleep(3)
                    # Post end-of-session metrics
                    url = args.server + "/sessions/end"
                    players = []
                    for pid in [1, 2]:
                        players.append({
                            "player_id": pid,
                            "score": random.randint(0, 100),
                            "play_time_sec": random.randint(30, 300),
                            "metrics": {"shots": random.randint(1, 50)}
                        })
                    payload = {"session_id": session_id, "game_metrics": {"note": "simulated"}, "players": players}
                    headers = {"X-API-Key": args.api_key} if args.api_key else {}
                    r = requests.post(url, json=payload, headers=headers)
                    print("End session resp:", r.status_code, r.text)

    asyncio.run(run())

if __name__ == "__main__":
    main()
