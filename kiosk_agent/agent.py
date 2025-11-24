
import asyncio
import websockets
import serial
import yaml
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

async def main():
    cfg = load_config()
    device = cfg.get("serial_device", "/dev/ttyUSB0")
    baud = int(cfg.get("baudrate", 9600))
    try:
        ser = serial.Serial(device, baudrate=baud, timeout=0.1)
        print(f"Opened serial {device} @ {baud}")
    except Exception as e:
        print(f"Failed to open serial device {device}: {e}")
        ser = None

    async def handler(websocket):
        print("Web client connected")
        try:
            while True:
                if ser:
                    line = ser.readline().decode(errors="ignore").strip()
                    if line:
                        await websocket.send(line)
                await asyncio.sleep(0.02)
        except websockets.exceptions.ConnectionClosed:
            print("Web client disconnected")

    print("Starting kiosk agent WS on ws://127.0.0.1:8765")
    async with websockets.serve(lambda ws, path=None: handler(ws), "127.0.0.1", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
