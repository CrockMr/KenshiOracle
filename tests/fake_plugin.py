"""Protocol fixture. Deliberately does not emulate or validate any game API."""
import asyncio
import json


class FakePlugin:
    def __init__(self, mode='normal'):
        self.mode = mode
        self.frame = 0
        self.calls = []

    async def __aenter__(self):
        self.server = await asyncio.start_server(self.handle, '127.0.0.1', 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *args):
        self.server.close()
        await self.server.wait_closed()

    async def handle(self, reader, writer):
        try:
            while raw := await reader.readline():
                req = json.loads(raw)
                self.calls.append(req['command'])
                if self.mode == 'hang':
                    await reader.read()
                    return
                if self.mode not in ('menu', 'renderer_frozen', 'loading'):
                    self.frame += 1
                command = req['command']
                if command in ('ping', 'heartbeat'):
                    result = dict(plugin_version='fake', game_version='fake', frame=self.frame, timestamp_ms=123)
                    result.update(world_ready=self.mode != 'menu', paused=False, frame_speed_multiplier=1)
                    result['loading'] = self.mode == 'loading'
                    if self.mode == 'service_zero':
                        result['service_frame'] = 0
                    if self.mode.startswith('renderer_'):
                        result.update(frame=0, service_frame=self.frame, service_timestamp_ms=456)
                elif command == 'get_frame_stats':
                    result = dict(count=req['params']['n'], mean_ms=16, median_ms=16, p95_ms=20, p99_ms=22, max_ms=24, systems={})
                elif command == 'list_characters':
                    result = dict(characters=[dict(name='Test', faction='Test', position=[1, 2, 3])][:req['params']['limit']])
                else:
                    result = req['params']
                reply = dict(id=req['id'], result=result)
                if command == 'load_save':
                    reply = dict(id=req['id'], error=dict(code='unsupported', message='safe loader unknown'))
                if self.mode == 'wrong_id':
                    reply['id'] = 'wrong'
                wire = json.dumps(reply).encode() + b'\n'
                if self.mode == 'invalid':
                    wire = b'not json\n'
                # Deliberately fragmented to exercise stream framing.
                writer.write(wire[:3])
                await writer.drain()
                writer.write(wire[3:])
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
