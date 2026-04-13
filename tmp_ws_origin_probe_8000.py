from websockets.sync.client import connect

for origin in (None, 'http://localhost:5173', 'http://127.0.0.1:5173'):
    try:
        kwargs = {}
        if origin:
            kwargs['origin'] = origin
        with connect('ws://127.0.0.1:8000/ws/live-buysell', **kwargs) as ws:
            msg = ws.recv(timeout=5)
            print('OK', origin, str(msg)[:140])
    except Exception as e:
        print('ERR', origin, type(e).__name__, e)
