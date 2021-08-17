from . import workers
from . import websocket
import ujson as json
import asyncio
import time

def wait_time_for(queue_size: int) -> float:
    if queue_size > 30:
        return 1.0
    elif queue_size > 20:
        return 0.5
    elif queue_size> 10:
        return 0.25
    return 0.15


async def send_no_build_env_error(ws: websocket.WebSocket):
    msg = {
        'error': '1', # TODO: describe errors enum
        'description': 'No build_env query param set',
        'stage': 'backend',
    }
    await ws.send_json(msg)


async def send_no_request_id_error(ws: websocket.WebSocket):
    msg = {
        'error': '1', # TODO: describe errors enum
        'description': 'No X-Request-ID header set',
        'stage': 'backend',
    }
    await ws.send_json(msg)


async def send_cant_build_bridge_error(build_env: str, ws: websocket.WebSocket):
    msg = {
        'error': '1', # TODO: describe errors enum
        'description': f'Failed to build a bridge, no workers with build_env: {build_env} found',
        'stage': 'backend',
    }
    await ws.send_json(msg)


async def wait_in_queue(bridge: workers.Bridge, ws: websocket.WebSocket):
    last_feedback_time = time.time()
    while True:
        q = bridge.queue_number()
        if q > 0:
            t = time.time()
            if t - last_feedback_time > 1.0:
                print(f"/run: client {bridge.request_id} is number {q} in a queue")
                await ws.send_json({"queue": q})
                last_feedback_time = t
            await asyncio.sleep(wait_time_for(q))
        else:
            break


async def receive_from_client_loop(request_id: str, bridge: workers.Bridge, ws: websocket.WebSocket):
    # loop for messages from the client
    while True:
        msg: str = await ws.receive_text()
        msg_json = json.loads(msg)
        request_id = msg_json["request_id"]

        print(f"/run: sending message from request_id: {request_id} to worker {bridge.worker.worker_id}")
        bridge.send_to_worker(msg)


async def handle(ws: websocket.WebSocket):
    await ws.accept()

    build_env = ws.query_params.get('build_env', '')
    if build_env == '':
        return await send_no_build_env_error(ws)

    request_id = ws.query_params.get('request_id', '') #ws.headers["X-Request-ID"]
    if request_id == '':
        return await send_no_request_id_error(ws)

    print(f'/run: accepted a connection with a client request_id: {request_id}, wanted build_env: {build_env}')

    bridge = workers.manager().make_bridge(request_id, build_env)
    if bridge is None:
        return await send_cant_build_bridge_error(build_env, ws)

    receive_task = None
    try:
        # wait in a queue if there is
        await wait_in_queue(bridge, ws)
        print(f'{request_id} has started being served')

        # separate loop for messages from the client
        receive_task = asyncio.create_task(receive_from_client_loop(request_id, bridge, ws))

        # the initial message must be {"command": "new", "request_id": "..."}
        bridge.send_to_worker({
            'command': 'new',
            'request_id': request_id
        })

        # messages from the worker
        while True:
            msg: str = await bridge.receive_from_worker()
            msg_json = json.loads(msg)
            msg_request_id = msg_json["request_id"]
            assert msg_request_id == request_id

            print(f'/run: received message from worker: {bridge.worker.worker_id} to request_id: {request_id}')

            await ws.send_text(msg)

            if msg_json.get("finish", None) == True:
                print(f'/run: received finish from worker: {bridge.worker.worker_id} to request_id: {request_id}, will close')
                break
    except websocket.DisconnectError:
        print(f'/run: client {request_id} disconnected')
    except Exception as e:
        print(f'/run: exception {e}')

    if receive_task:
        receive_task.cancel()
    await ws.close()
    bridge.close()
    workers.manager().remove_bridge(bridge)
    print(f'/run: closed {request_id}')
