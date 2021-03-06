from . import workers
from . import websocket
from . import test_cases
import ujson as json
import asyncio
import time


MAX_WAIT_IN_FIRST_LINE = 20.0 # in seconds

def wait_time_for(queue_size: int) -> float:
    if queue_size > 30:
        return 1.0
    elif queue_size > 20:
        return 0.5
    elif queue_size > 10:
        return 0.25
    return 0.15


async def send_missing_query_parameter_error(param_name: str, ws: websocket.WebSocket):
    msg = {
        'description': f'No {param_name} query parameter set',
        'stage': 'backend',
    }
    await ws.send_json(msg)


async def send_cant_build_bridge_error(build_env: str, ws: websocket.WebSocket):
    msg = {
        'description': f'Failed to build a bridge, no workers with build_env: {build_env} found',
        'stage': 'backend',
    }
    await ws.send_json(msg)


async def send_worker_disconnected_error(ws: websocket.WebSocket):
    msg = {
        'description': 'Worker has disconnected, please, try again',
        'stage': 'backend',
    }
    await ws.send_json(msg)


async def wait_in_queue(request_id: str, build_env: str, ws: websocket.WebSocket):
    last_feedback_time = time.time() - 10.1
    # wait in a queue and periodically send a position in the queue to the client
    while True:
        q = workers.manager().queue_number(request_id, build_env)
        if q > 0:
            t = time.time()
            if t - last_feedback_time > 2.0:
                print(f'/run: request {request_id} is number {q} in a queue')
                await ws.send_json({'queue': q + 1}) # send queue position to the client
                last_feedback_time = t
            await asyncio.sleep(wait_time_for(q + 1))
        else:
            break
    # we're number 1 in the queue, but probably we'll need to wait for a free worker
    start_time = time.time()
    while True:
        bridge = workers.manager().make_bridge(request_id, build_env)
        if bridge is None: # can't make a bridge, every worker is busy
            t = time.time()
            if t - last_feedback_time > 2.0:
                print(f"/run: request {request_id} is number 1 in a queue")
                await ws.send_json({'queue': 1})
                last_feedback_time = t

            if t - start_time > MAX_WAIT_IN_FIRST_LINE:
                await send_cant_build_bridge_error(build_env, ws)
                raise Exception('couldn\'t build a bridge in a reasonable time')
            await asyncio.sleep(0.01)
        else:
            return bridge


async def receive_from_client_loop(request_id: str, bridge: workers.Bridge, ws: websocket.WebSocket):
    # loop for messages from the client
    while True:
        msg: str = await ws.receive_text()
        msg_json = json.loads(msg) # TODO: delete because it's wasty
        request_id = msg_json['request_id']

        print(f'/run: sending message from request {request_id} to worker {bridge.worker.worker_id}: {msg[:38]}')
        bridge.send_to_worker(msg)


async def send_test_cases(bridge: workers.Bridge, request_id: str, task_id: str):
    print(f'/run: sending test suite')
    test_cases_json = json.loads(test_cases.load_for(task_id))
    test_cases_json['request_id'] = request_id
    bridge.send_to_worker(test_cases_json)


async def handle(ws: websocket.WebSocket):
    await ws.accept()

    task_id = ws.query_params.get('task_id', '')
    if task_id == '':
        return await send_missing_query_parameter_error('task_id', ws)

    target = ws.query_params.get('target', '')
    if target == '':
        return await send_missing_query_parameter_error('target', ws)

    build_env = ws.query_params.get('build_env', '')
    if build_env == '':
        return await send_missing_query_parameter_error('build_env', ws)

    request_id = ws.query_params.get('request_id', '')
    if request_id == '':
        return await send_missing_query_parameter_error('request_id', ws)

    print(f'/run: accepted a connection with a request {request_id}, task_id: {task_id}, build_env: {build_env}, target: {target}')

    workers.manager().put_in_queue(request_id, build_env)

    receive_task = None
    bridge = None
    try:
        bridge = await wait_in_queue(request_id, build_env, ws)
        worker_id = bridge.worker.worker_id
        print(f'/run: request {request_id} has started being served')

        await ws.send_text('{"ping":"1"}') # it's hack to have an exception here if the connection is closed for some reason

        # separate loop for messages from the client
        receive_task = asyncio.create_task(receive_from_client_loop(request_id, bridge, ws))

        # the initial message must be {"command": "new", "request_id": "..."}
        bridge.send_to_worker({
            'command': 'new',
            'request_id': request_id,
            'target': target
        })

        # send test cases if needed
        if 'tests' in target:
            await send_test_cases(bridge, request_id, task_id)

        # messages from the worker
        while True:
            msg: str = await bridge.receive_from_worker()
            msg_json = json.loads(msg)
            msg_request_id = msg_json["request_id"]
            assert msg_request_id == request_id

            print(f'/run: received message from worker {worker_id} to request {request_id}: {msg[:38]}')

            await ws.send_text(msg)

            if msg_json.get("finish", None) == True:
                print(f'/run: received finish from worker {worker_id} to request {request_id}, will close')
                break
    except websocket.DisconnectError:
        print(f'/run: request {request_id} disconnected')
    except workers.DisconnectError:
        print(f'/run: request {request_id} found out that worker disconnected')
        try:
            await send_worker_disconnected_error(ws)
        except websocket.DisconnectError:
            print(f'/run: request {request_id} disconnected too')
    except Exception as e:
        print(f'/run: request {request_id}, exception: {e}')

    if receive_task:
        receive_task.cancel()
    await ws.close()
    if bridge:
        bridge.close()
        workers.manager().remove_bridge(bridge)
    print(f'/run: closed request {request_id}')
