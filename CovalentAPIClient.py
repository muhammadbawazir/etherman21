from httpx import AsyncClient
import asyncio

from loguru import logger
from currency_symbols import CurrencySymbols as CS
import pandas as pd

# from erc20_worker import ERC20_Worker
"""

APIs:

- Get token balances for address: v1/{chain_id}/address/{address}/balances_v2/
- Get Transactions: /v1/{chain_id}/address/{address}/transactions_v2/
- Get ERC20 Token Transfer: /v1/{chain_id}/address/{address}/transfers_v2/

Response:

parameter : chain_id, address, currency

response structure:
{
	all_balance : $123123,  [all balance: sum( items: quote))]
	currency : usd,
	balance : {
	# token balance items, exclude 'nft'
	}
	nft : {
	# token balance items where type='nft'
	},
	
	transaction : {
	 # transactions items
	 tanggal, signet_at, tx_hash, from_address, to_address, successfull
	},
	
	erc20transaction : {
	# erc20 items by contract address
	}
}
"""

class CovalentAPIClient:
    ENDPOINTS = { 'base': "https://api.covalenthq.com",
                  'token_balances': '/v1/{chain_id}/address/{address}/balances_v2/',
                  'transactions': '/v1/{chain_id}/address/{address}/transactions_v2/',
                  'portfolio': '/v1/{chain_id}/address/{address}/portfolio_v2/',
                  'erc20_token': '/v1/{chain_id}/address/{address}/transfers_v2/'
               }

    CURRENCY_TO_SIGN = {'usd' : 'USD', 'eur': 'EUR', 'jpy': 'JPY'}
    HEADER ={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5)\
            AppleWebKit/537.36 (KHTML, like Gecko) Cafari/537.36'}

    NUM_TO_MONTH = {'01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr', '05': 'May', '06': 'Jun', '07': 'Jul',
                    '08': 'Aug', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'}

    async def get_all(self, chain_id, address, currency='usd'):
        response = {}

        currency_key, response['currency'] = self.get_currency(currency)
        query_param = {'quote-currency': currency_key}
        token_balances_url = self.get_token_balances_url(chain_id, address, query_param)
        transactions_url = self.get_transactions_url(chain_id, address, query_param)
        portfolio_url = self.get_portfolio(chain_id, address, query_param)

        urls = [portfolio_url, transactions_url, token_balances_url]
        # TODO: failed request retry
        responses = await asyncio.gather(*map(self.__get_request_async, urls))

        status_codes = [responses[0].status_code, responses[1].status_code, responses[2].status_code]
        is_not_exist = status_codes[0]== 400 and status_codes[1] == 400 and status_codes[2] == 400
        if is_not_exist:
            return {'balance': []}

        is_success = status_codes[0]==200 and status_codes[1]==200 and status_codes[2]==200
        if not is_success:
            return {'error': 1}

        portfolio, transactions, token_balances = responses[0].json(), responses[1].json(), responses[2].json()

        transaction_items = transactions['data'].get('items', [])
        response['transactions'] = self.__parse_transcation(transaction_items)

        portfolio_response = []
        for item in portfolio.get('items', []):
            entity = {'contract_name': item['contract_name'], 'data': [], 'date_converted': []}
            contract_decimal = item['contract_decimals']

            for balances in item['holdings']:
                entity['data'].append(round(float(balances['close']['balance']) / (pow(10, contract_decimal)), 4))
                date_converted = '-'
                if balances["timestamp"]:
                    date_converted = balances["timestamp"][5:10].split('-')
                    date_converted[0] = self.NUM_TO_MONTH.get(date_converted[0], 'None')
                    date_converted = ' '.join(date_converted)

                entity['date_converted'].append(date_converted)

            entity['data'].reverse()
            entity['date_converted'].reverse()

            portfolio_response.append(entity)

        response['portfolio'] = portfolio_response

        token_balances_items = token_balances['data'].get('items', {})
        if token_balances_items:
            response['balance'], response['all_balance'], response['nft'] = self.__items_and_sum_balances(token_balances_items, exclude_type=['nft'])
        else:
            response['all_balance'] = 0
            response['nft'] = []
            return response

        return response

    async def __get_request_async(self, url):
        async with AsyncClient(event_hooks={'request': [self.log_request], 'response': [self.log_response]}, timeout=30) as client:
            return await client.get(url, headers=self.HEADER)

    def get_token_balances_url(self, chain_id, address, query_param=None, nft=True): # query_param currency
        end_point = self.ENDPOINTS['base'] + self.ENDPOINTS['token_balances'].format(chain_id=chain_id,
                                                                                     address=address)
        if nft:
            query_param['nft'] = True

        if query_param:
            end_point += '?' + self.__make_query_string(query_param)
            query_param.pop('nft')

        return end_point

    def get_transactions_url(self, chain_id, address, query_param=None): # query_param currency
        end_point = self.ENDPOINTS['base'] + self.ENDPOINTS['transactions'].format(chain_id=chain_id,
                                                                                     address=address)
        if query_param:
            end_point += '?' + self.__make_query_string(query_param)

        return end_point

    def get_portfolio(self, chain_id, address, query_param=None):
        end_point = self.ENDPOINTS['base'] + self.ENDPOINTS['portfolio'].format(chain_id=chain_id,
                                                                                   address=address)
        if query_param:
            end_point += '?' + self.__make_query_string(query_param)

        return end_point

    def __make_query_string(self, query_param):
        query = []
        for key, value in query_param.items():
            query.append(str(key) + '=' + str(value))
        query = '&'.join(query)

        return query

    def __items_and_sum_balances(self, items, exclude_type=None):
        if not exclude_type:
            exclude_type = []

        total_balance, included_items, excluded_items = 0, [], []
        for item in items:
            if item['type'] in exclude_type:
                excluded_items.append(item)
                continue

            total_balance += item['quote']
            item['balance_converted'] ='{:.4f}'.format( round(float(item['balance']) / pow(10, item['contract_decimals']), 4) )
            included_items.append(item)

        return included_items, total_balance, excluded_items

    async def log_request(self, request):
        logger.info(f"Request event hook: {request.method} {request.url} - Waiting for response")

    async def log_response(self, response):
        request = response.request
        logger.info(f"Response event hook: {request.method} {request.url} - Status {response.status_code}")

    def __parse_transcation(self, items, raw=False):
        response = []
        if not items:
            return response

        is_included = {}
        for item in items:
            if is_included.get(item['tx_hash'], False):
                continue

            entity = {'block_signet_at': item['block_signed_at'], 'tx_hash': item['tx_hash'],
                          'from_address': item['from_address'], 'to_address': item['to_address'],
                          'successful': item['successful']}

            response.append(entity)

        return response

    def get_currency(self, currency):
        currency = currency.lower()
        is_currency_included = self.CURRENCY_TO_SIGN.get(currency, False)
        if not is_currency_included:
            currency = 'usd'
        currency_key = self.CURRENCY_TO_SIGN.get(currency)
        currency_symbol = CS.get_symbol(currency_key)

        return currency_key, currency_symbol

    async def get_balance_csv(self, chain_id, address):
        token_balances_url = self.get_token_balances_url(chain_id, address, nft=False)
        responses = await asyncio.gather(*map(self.__get_request_async, [token_balances_url]))

        status_code = responses[0].status_code
        is_not_exist = status_code == 400
        if is_not_exist:
            return False

        is_success = status_code==200
        if not is_success:
            return False

        token_balances = responses[0].json()

        token_balances_items = token_balances['data'].get('items', {})
        if token_balances_items:
            filtered_items = self.__parse_balances(token_balances_items, exclude_type=['nft'])
        else:
            return {"error": "items empty"}

        data = pd.DataFrame(filtered_items)
        return data.to_csv(index=False)

    async def get_transactions_csv(self, chain_id, address):
        transactions_url = self.get_transactions_url(chain_id, address)
        responses = await asyncio.gather(*map(self.__get_request_async, [transactions_url]))

        status_code = responses[0].status_code
        is_not_exist = status_code == 400
        if is_not_exist:
            return False

        is_success = status_code==200
        if not is_success:
            return False

        transactions = responses[0].json()

        transactions_items = transactions['data'].get('items', {})
        if transactions_items:
            items = self.__parse_transaction_csv(transactions_items)
        else:
            return {"error": "items empty"}

        data = pd.DataFrame(items)
        return data.to_csv(index=False)

    def __parse_transaction_csv(self, items):
        data = []
        for item in items:
            entity = item

            log_events = entity.pop('log_events', [])
            count_log_event = 1
            while log_events:
                entity['log_event_{}'.format(count_log_event)] = log_events.pop(0)
                count_log_event+= 1

            data.append(entity)

        return data

    def __parse_balances(self, items, exclude_type=None):
        if not exclude_type:
            exclude_type = []

        included_items = []
        for item in items:
            if item['type'] in exclude_type:
                continue

            item.pop('nft_data')
            included_items.append(item)

        return included_items


# if __name__ == '__main__':
#     loop = asyncio.get_event_loop()
#
#     client = CovalentAPIClient()
#     response = loop.run_until_complete(client.get_all('43114', '0x1f351B1cAf0B7037353cd284a6a225CECCE5677b', 'usd'))
#     # response = loop.run_until_complete(client.get_all('1', 'demo.eth', 'usd'))
#     # print(response)
