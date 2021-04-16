from flask import Flask, request
import json

from CovalentAPIClient import CovalentAPIClient
import asyncio

app = Flask(__name__)
loop = asyncio.get_event_loop()

@app.route('/get_all/<chain_id>/<address>', methods=['GET'])
def get_all(chain_id=None, address=None):
    if not chain_id or not address:
        return json.dumps({})
    currency = request.args.get('currency', 'usd')

    api = CovalentAPIClient()

    response = loop.run_until_complete(api.get_all(chain_id, address, currency=currency))
    return json.dumps(response)

@app.route('/', methods=['GET'])
def home():
    response = {'text': 'temporary up'}
    return json.dumps(response)

if __name__=='__main__':
    app.run()
