import asyncio
import ujson as json
import random
from typing import List, Dict


class Worker:
    def __init__(self, worker_id: str, build_env: str):
        self.worker_id = worker_id
        self.build_env = build_env
        self.busy_factor = 0

    def inc_busy_factor(self):
        self.busy_factor += 1

    def dec_busy_factor(self):
        self.busy_factor -= 1
        assert(self.busy_factor >= 0)

    def available(self):
        return self.busy_factor == 0


class DisconnectError(Exception):
    pass


class Bridge:
    def __init__(self, worker: Worker, request_id: str):
        self.request_id = request_id
        self.worker = worker
        self.msgs_to_worker = asyncio.Queue()
        self.msgs_to_client = asyncio.Queue()
        self.worker.inc_busy_factor()
        self.disconnected = False

    async def receive_from_worker(self):
        msg = await self.msgs_to_client.get()
        # if it's a DisconnectError sent from the disconnect method, it means we should stop listening to, worker has disconnected
        if type(msg) == DisconnectError:
            raise msg
        return msg

    def send_to_worker(self, msg):
        if type(msg) == dict:
            msg = json.dumps(msg)
        self.msgs_to_worker.put_nowait(msg)

    def send_to_client(self, msg: str):
        self.msgs_to_client.put_nowait(msg)

    def close(self):
        if self.msgs_to_client.qsize() > 0 or self.msgs_to_worker.qsize() > 0:
            print(f'Warning: a bridge from request_id {self.request_id} to worker {self.worker.worker_id} has pending messages: {self}')
        self.worker.dec_busy_factor()
        self.worker = None
    
    def disconnect(self):
        self.msgs_to_client.put_nowait(DisconnectError())
        self.disconnected = True

    def __repr__(self):
        return f'(request_id: {self.request_id}, worker: {self.worker.worker_id}, msgs_to_client: {self.msgs_to_client.qsize()}, msgs_to_worker: {self.msgs_to_worker.qsize()})'


class WorkersManager:
    def __init__(self):
        self.workers = []
        self.bridges = []
        self.wait_queue: Dict[str, List[str]] = {}

    def register(self, worker_id: str, build_env: str):
        if len(self.workers) > 0 and next(w for w in self.workers if w.worker_id == worker_id) is not None:
            print(f'Error: worker {worker_id} has alredy been registered')
            return
        self.workers.append(Worker(worker_id, build_env))

    def unregister(self, worker_id: str):
        worker = next(w for w in self.workers if w.worker_id == worker_id) if len(self.workers) > 0 else None
        if worker is None:
            print(f'Error: couldn\'t unregister worker {worker_id} with build_env {build_env}')

        self.workers.remove(worker)

        bridges = (b for b in self.bridges if b.worker.worker_id == worker_id)
        for b in bridges:
            b.disconnect()

    # called from /bridge
    async def receive_for_worker(self, worker_id: str) -> str:
        while True:
            # find all bridges with the given worker_id
            bridges = [b for b in self.bridges if b.worker.worker_id == worker_id and not b.msgs_to_worker.empty()]
            if len(bridges) == 0:
                await asyncio.sleep(0.05) # TODO: block until event?
                continue

            # pick a random one and get a message from it's queue
            bridge = random.choice(bridges)
            msg = bridge.msgs_to_worker.get_nowait()
            return msg

    # called from /bridge
    def send_to_client(self, request_id: str, worker_id: str, msg: str):
        bridge = next(b for b in self.bridges if b.request_id == request_id and b.worker.worker_id == worker_id) if len(self.bridges) > 0 else None
        if bridge:
            bridge.send_to_client(msg)
        else:
            raise Exception('couldn\'t find a bridge between request {request_id} and worker {worker_id}')

    def make_bridge(self, request_id: str, build_env: str) -> Bridge:
        assert(len(self.wait_queue[build_env]) > 0 and self.wait_queue[build_env][0] == request_id)
        # pick a random free worker with matching `build_env`
        if len(self.workers) == 0:
            return None
        worker = None
        shift = random.randint(0, len(self.workers) - 1)
        for i in range(len(self.workers)):
            w = self.workers[(i + shift) % len(self.workers)]
            if w.build_env == build_env and w.available():
                worker = w
                break
        if worker is None:
            return None

        # create a bridge instance
        bridge = Bridge(worker, request_id)
        self.bridges.append(bridge)

        # remove the request from a wait queue
        assert(len(self.wait_queue[build_env]) > 0 and self.wait_queue[build_env].index(request_id) == 0)
        self.wait_queue[build_env].remove(request_id)

        print(f'Made a bridge from {request_id} to {worker.worker_id}')
        return bridge

    def remove_bridge(self, bridge: Bridge):
        self.bridges.remove(bridge)
    
    def put_in_queue(self, request_id: str, build_env: str):
        if build_env not in self.wait_queue:
            self.wait_queue[build_env] = [request_id]
        else:
            self.wait_queue[build_env].append(request_id)

    # what position the client is in the queue?
    def queue_number(self, request_id: str, build_env: str):
        return self.wait_queue[build_env].index(request_id)


instance = WorkersManager()

def manager():
    return instance
