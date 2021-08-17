from . import workers
from . import websocket
import uuid
import ujson as json
import asyncio

async def receive_from_client_loop(worker_id: str, ws: websocket.WebSocket):
    try:
        while True:
            msg: str = await workers.manager().receive_for_worker(worker_id)
            msg_json = json.loads(msg) # TODO: only do that in DEBUG
            request_id = msg_json["request_id"]

            print(f"/bridge: sending message from request_id {request_id} to worker {worker_id}")
            await ws.send_text(msg)

    except asyncio.CancelledError:
        pass


async def handle(ws: websocket.WebSocket):
    await ws.accept()

    worker_id = str(uuid.uuid4())
    build_env = ws.query_params.get('build_env', '')
    if build_env == '':
        pass # TODO: close connection with error

    client_addr = f'{ws.scope["client"][0]}:{ws.scope["client"][1]}'
    print(f"/bridge: accepted a connection with a worker id: {worker_id}, ip addr: {client_addr}, build_env: {build_env}")

    workers.manager().register(worker_id, build_env)

    receive_task = asyncio.create_task(receive_from_client_loop(worker_id, ws))

    try:
        while True:
            msg: str = await ws.receive_text()
            msg_json = json.loads(msg)
            request_id = msg_json["request_id"]

            print(f"/bridge: received message from worker {worker_id} to request_id {request_id}: {msg[:24]}")

            workers.manager().send_to_client(request_id, worker_id, msg)

    except websocket.DisconnectError:
        print(f'/bridge: worker {worker_id} disconnected')
    except Exception as e:
        print(f'/brigde: exception {e}')

    # TODO: unregister on connection close
    receive_task.cancel()
    await receive_task
    workers.manager().unregister(worker_id, build_env)
    print(f'/bridge: exit for {worker_id}')
