import uvicorn

if __name__ == "__main__":
    uvicorn.run("practicode_backend.asgi:application", host="127.0.0.1", port=8000, log_level="info", reload=True, ws_ping_interval=2.0)
