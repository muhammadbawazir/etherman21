import os
from flask import Flask, request
from flask_cors import CORS
from loguru import logger
import json

from CovalentAPIClient import CovalentAPIClient
import asyncio

app = Flask(__name__)
CORS(app)

@app.route('/get_all/<chain_id>/<address>', methods=['GET'])
def get_all(chain_id=None, address=None):
    loop = asyncio.new_event_loop()
    if not chain_id or not address:
        return json.dumps({'balance': []})

    currency = request.args.get('currency', 'usd')

    api = CovalentAPIClient()
    response = loop.run_until_complete(api.get_all(chain_id, address, currency=currency))

    return json.dumps(response, ensure_ascii=False)

@app.route('/', methods=['GET'])
def home():
    response = {'text': 'temporary up'}
    return json.dumps(response)

if __name__=='__main__':
    app.run(debug=True)