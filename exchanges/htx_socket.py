import threading  # Убедитесь, что threading импортирован!
import time
import websocket
import json
import re
import requests
from functools import partial

class HtxSocket:
    def __init__(self):
        try:
            self.mTickers = {}
            self.ticker_socket = {}
            self.start()
        except Exception as e:
            print(e)

    def on_message(self, _wsa, wsData, prm):
        varData = json.loads(wsData)
        if 'op' in varData:
            if varData['op'] == 'subscribe' and varData['success'] == False:
                mPairs = re.findall(r'\[([^]]*)\]', varData['ret_msg'])
                for elem in mPairs:
                    del(self.ticker_socket[prm['key']]['listPair'][elem])

                if len(self.ticker_socket[prm['key']]['listPair']) == 0:
                    self.ticker_socket[prm['key']]['exit'] = 'true'
                    self.ticker_socket[prm['key']]['status'] = 'off'

                _wsa.close()
        else:
            self.mTickers[varData['data']['symbol']] = varData['data']

    def on_close(self, _wsa, wsData, prm):
        _wsa.close()
        self.ticker_socket[prm['key']]['status'] = 'off'

    def on_open(self, _wsa, prm):
        try:
            args = list(self.ticker_socket[prm['key']]['listPair'].values())
            _wsa.send(json.dumps({"op": "subscribe", "args": args}))
        except Exception as e:
            _wsa.close()

    def runWebSockPl(self, key):
        while True:
            try:
                wss = 'wss://api.htx.com/ws'  # URL для HTX
                wsa = websocket.WebSocketApp(wss,
                                              on_open=partial(self.on_open, prm={'key': key}),
                                              on_message=partial(self.on_message, prm={'key': key}),
                                              on_error=partial(self.on_close, prm={'key': key}),
                                              on_close=partial(self.on_close, prm={'key': key}))

                self.ticker_socket[key]['connect'] = wsa
                self.ticker_socket[key]['status'] = 'on'

                print(f'Установлено соединение WebSocket для ключа {key} с HTX')

                wsa.run_forever()
                if self.ticker_socket[key]['exit'] == 'true':
                    break
                raise Exception('Exit')
            except Exception as e:
                print(f'Разрыв соединения WebSocket для ключа {key} с HTX')
                self.ticker_socket[key]['status'] = 'off'
                time.sleep(10)

    def start(self):
        response = requests.get("https://api.htx.com/api/v1/market/tickers")
        data = response.json()

        i = 1
        listPair = {}
        for elem in data['result']:
            listPair['tickers.'+elem['symbol']] = 'tickers.'+elem['symbol']
            if len(listPair) >= 10:
                key = str(i)
                self.ticker_socket[key] = {'connect': '', 'status': 'off', 'exit': 'false', 'listPair': listPair}
                listPair = {}

                ws = threading.Thread(target=self.runWebSockPl, kwargs={'key': key})
                ws.setDaemon(True)
                ws.start()

                i = i + 1

        if len(listPair) > 0:
            key = str(i)
            self.ticker_socket[key] = {'connect': '', 'status': 'off', 'exit': 'false', 'listPair': listPair}

            ws = threading.Thread(target=self.runWebSockPl, kwargs={'key': key})
            ws.setDaemon(True)
            ws.start()

        # Вывод данных
        while True:
            time.sleep(10)
            print(self.mTickers)


if __name__ == "__main__":
    HtxSocket()
