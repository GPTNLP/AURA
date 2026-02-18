from flask import Flask, request

app = Flask(__name__)

@app.post("/move")
def move():
    data = request.json
    cmd = data.get("cmd")
    print("ROBOT COMMAND RECEIVED:", cmd)

    # TODO: send serial command to ESP32
    # serial.write(cmd.encode())

    return {"status": "ok", "received": cmd}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
