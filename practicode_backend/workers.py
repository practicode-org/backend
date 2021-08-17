import asyncio
import ujson as json
import random


class Worker:
    def __init__(self, worker_id: str, build_env: str):
        self.worker_id = worker_id
        self.build_env = build_env
        self.queue: List[str] = [] # list of request_ids # TODO: replace with real queue type?


class Bridge:
    def __init__(self, worker: Worker, request_id: str):
        self.request_id = request_id
        self.worker = worker
        self.msgs_to_worker = asyncio.Queue()
        self.msgs_to_client = asyncio.Queue()

        worker.queue.append(request_id)

    def queue_number(self):
        assert len(self.worker.queue) > 0
        return self.worker.queue.index(self.request_id)

    async def receive_from_worker(self):
        return await self.msgs_to_client.get()

    def send_to_worker(self, msg):
        if type(msg) == dict:
            msg = json.dumps(msg)
        assert len(self.worker.queue) > 0 and self.worker.queue[0] == self.request_id
        self.msgs_to_worker.put_nowait(msg)

    def send_to_client(self, msg: str):
        self.msgs_to_client.put_nowait(msg)

    def close(self):
        if self.msgs_to_client.qsize() > 0 or self.msgs_to_worker.qsize() > 0:
            print(f'Warning: bridge has pending messages: {self}')
        assert len(self.worker.queue) > 0 and self.worker.queue.index(self.request_id) != -1
        self.worker.queue.remove(self.request_id)

    def __repr__(self):
        return f'(request_id: {self.request_id}, worker_id: {self.worker.worker_id}, msgs_to_client: {self.msgs_to_client.qsize()}, msgs_to_worker: {self.msgs_to_worker.qsize()})'


class WorkersManager:
    def __init__(self):
        self.workers = []
        self.bridges = []

    def register(self, worker_id: str, build_env: str):
        self.workers.append(Worker(worker_id, build_env))
        # TODO: check if already exists

    def unregister(self, worker_id: str, build_env: str):
        # TODO: check if exists
        for i in range(len(self.workers)):
            w = self.workers[i]
            if w.worker_id == worker_id and w.build_env == build_env:
                self.workers.pop(i)
                return
        print(f'Error: couldn\'t unregister worker {worker_id} with build_env {build_env}')

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
        for b in self.bridges:
            if b.request_id == request_id and b.worker.worker_id == worker_id:
                b.send_to_client(msg)
                return
        #TODO: raise an Error
        raise Exception('wtf 1')

    def make_bridge(self, request_id: str, wants_build_env: str) -> Bridge:
        # 1) find all workers with `wants_build_env`
        workers = [w for w in self.workers if w.build_env == wants_build_env]
        if len(workers) == 0:
            return None

        # 2) pick the one with the smallest queue
        worker = min(workers, key=lambda w: len(w.queue))

        # 3) create a bridge instance
        bridge = Bridge(worker, request_id)
        self.bridges.append(bridge)
        print(f'Made a bridge from {request_id} to {worker.worker_id}')
        return bridge

    def remove_bridge(self, bridge):
        self.bridges.remove(bridge)


instance = WorkersManager()

def manager():
    return instance
