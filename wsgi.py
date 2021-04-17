import os
from flask import Flask, request
from flask_caching import Cache
from flask_cors import CORS

import json

from CovalentAPIClient import CovalentAPIClient
import asyncio

config = {
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_THRESHOLD": 10,
    "CACHE_DEFAULT_TIMEOUT": 120
}

app = Flask(__name__)
app.config.from_mapping(config)
cache = Cache(app)

CORS(app)

@app.route('/get_all/<chain_id>/<address>', methods=['GET'])
def get_all(chain_id=None, address=None):
    if not chain_id or not address:
        return json.dumps({'balance': []})
    loop = asyncio.new_event_loop()

    currency = request.args.get('currency', 'usd')
    api = CovalentAPIClient()

    key = ':'.join([chain_id, address])
    response = cache.get(key)
    if response:
        _, response['currency'] = api.get_currency(currency)
    else:
        response = loop.run_until_complete(api.get_all(chain_id, address, currency=currency))
        cache.set(key, response)

    return json.dumps(response, ensure_ascii=False)

@app.route('/', methods=['GET'])
def home():
    response = {'text': 'temporary up'}
    return json.dumps(response)

if __name__=='__main__':
    app.run(debug=True)