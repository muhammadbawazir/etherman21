import os
from flask import Flask, request
from flask_caching import Cache
from flask_cors import CORS

import asyncio
from threading import Thread
from loguru import logger

import json
import time
from CovalentAPIClient import CovalentAPIClient


config = {
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_THRESHOLD": 20,
    "CACHE_DEFAULT_TIMEOUT": 300
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

    key , latest_update_key = get_redis_keys(chain_id, address)
    response = cache.get(key)
    if response:
        _, response['currency'] = api.get_currency(currency)
        thread = Thread(target=update_cache, args=(chain_id, address))
        thread.daemon = True
        thread.start()
    else:
        response = loop.run_until_complete(api.get_all(chain_id, address, currency=currency))
        if 'portfolio' in response.keys():
            cache.set(key, response)
            cache.set(latest_update_key, time.time())

    return json.dumps(response, ensure_ascii=False)

@app.route('/', methods=['GET'])
def home():
    response = {'text': 'temporary up'}
    return json.dumps(response)

def update_cache(chain_id, address, currency='usd'):
    key, latest_updated = get_redis_keys(chain_id, address)

    logger.info("updating cache for key: {}".format(key))
    if time.time() - cache.get(latest_updated) > 60.0:
        loop = asyncio.new_event_loop()

        api = CovalentAPIClient()
        response = loop.run_until_complete(api.get_all(chain_id, address, currency=currency))

        key = ':'.join([chain_id, address])
        if 'portfolio' in response.keys():
            cache.set(key, response)
            cache.set(latest_updated, time.time())

    logger.info("update cache for key: {} done".format(key))

def get_redis_keys(chain_id, address):
    return ':'.join([chain_id, address]), ':'.join([chain_id, address, 'time'])

if __name__=='__main__':
    app.run(debug=True)