from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
from json import loads
from urllib.parse import unquote_plus
from json import dumps
from time import time
app = FastAPI()


timeout=aiohttp.ClientTimeout(total=5)
async def lentaAPI(text):
    headers =  {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'ru,en;q=0.9',
        'Connection': 'keep-alive',
        'Host': 'lenta.com',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 YaBrowser/24.6.0.0 Safari/537.36',
        'X-Forward-Monolith': 'true',
        'X-Forward-Monolith': 'true',
        'X-NewRelic-ID': 'undefined',
        'newrelic': 'eyJ2IjpbMCwxXSwiZCI6eyJ0eSI6IkJyb3dzZXIiLCJhYyI6IjEwMDAwMDAiLCJhcCI6IjMzMjQxMTMiLCJpZCI6ImNlODlmMzlmMGM1ZmNjMTAiLCJ0ciI6IjRlYWQ2OGQ1OGQ3MzZmOGJkMGNmNWUwNmY3MTc4NmIwIiwidGkiOjE3MjE5MzA1MjgwNzN9fQ==',
    }
    params = {
        'value': text,
        'searchSource': 'Sku'
    }
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get('https://lenta.com/api/v1/search',headers=headers, params=params) as response:
            products = await response.json()
    items = [{
        "name": item['title'],
        "store_name": "Лента",
        "image_url": item['imageUrl'],
        "actionDate": "",
        "discountPercent": f"-{round(100 - float(item['price'])  * 100 / float(item['oldPrice']))}%" if item.get('oldPrice') else None,
        "discount": True if item['hasDiscount'] == 'True' else False,
        "price": item['cardPrice']['value'],
        "oldprice": item['regularPrice']['value'],
        'card_title' : 'Скидка по карте Лента',
        'category':item['gaCategory'],
    } for item in products['skus']]
    return items

        
async def ashanAPI(text):
    params = {
        'apiKey':'06U4652632',
        'strategy':'advanced_xname,zero_queries',
        'fullData':'true',
        'withCorrection':'true',
        'withFacets':'true',
        'treeFacets':'true',
        'regionId':'1',
        'useCategoryPrediction':'0.2',
        'preview':'false',
        'withSku':'false',
        'sort':'DEFAULT'
    }
    params["st"] = text
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get('https://sort.diginetica.net/search',params=params) as response:
            products = await response.json()
    items = [{
        "name": item['name'],
        "store_name": "Ашан",
        "image_url": item['image_url'],
        "actionDate": "",
        "discountPercent": f"-{round(100 - float(item['price'])  * 100 / float(item['oldPrice']))}%" if item.get('oldPrice') else None,
        "discount": True if item.get('oldPrice') else False,
        "price": item['price'],
        "oldprice": item.get('oldPrice')
    } for item in products['products']]
    return items


async def magnitAPI(name):
    headers = {
        'host':'magnit.ru',
        'x-device-tag':'disabled',
        'x-platform-version':'Windows Chrome 127',
        'x-app-version':'7.0.0',
        'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'content-type':'application/json',
        'accept':'application/json',
        'x-device-platform':'Web',
        'x-client-name':'magnit',
        'x-device-id':'1A5D0A5D-8C76-CEC4-D837-622100832565'
    }
    params = {"includeForAdults":True,"term":name,"pagination":{"offset":0,"limit":6},"sort":{"order":"desc","type":"popularity"},"storeCode":"559060","storeType":"1","catalogType":"1"}
    headers['Content-Length']= str(len(dumps(params)))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post('https://magnit.ru/webgate/v2/goods/search', headers=headers, json=params) as response:
            data = await response.json()
    items = [{
        "name": item['name'],
        "store_name": "Магнит",
        "image_url": item["gallery"][0]['url'],
        "actionDate": "",
        "discountPercent": f"-{round(100 - float(item['price'])  * 100 / float(item['promotion']['oldPrice']))}%" if item['promotion'].get('oldPrice') else None,
        "discount": True if item['promotion'].get('oldPrice') else False,
        "price": item['price']/100,
        "oldprice":  item['promotion']['oldPrice']/100 if item['promotion'].get('oldPrice') else None,
    } for item in data["items"]]
    return items

class PerekrestokAPI:
    def __init__(self):
        self.main_url = 'https://www.perekrestok.ru'
        self.token_url = 'https://www.perekrestok.ru/api/customer/1.4.1.0/catalog/product/feed'
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        self.perekrestok_token = ''

    async def get_token(self):
        headers = {
            'User-Agent': self.user_agent,
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.main_url, headers=headers) as response:
                session = response.cookies.get("session")
        session_cookie = loads(unquote_plus(session.value))
        return session_cookie['accessToken']

    async def get_data(self, token, name):
        headers = {
            "Authorization": f"Bearer {token}",
            "accept": "*/*",
            "accept-language": "ru,en;q=0.9",
            "sec-ch-ua": "\"Not.A/Brand\";v=\"8\", \"Chromium\";v=\"114\", \"YaBrowser\";v=\"23\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "x-app-version": "0.1.0",
            "x-device-id": "nk1kmh32na",
            "x-device-platform": "Web",
            "x-device-tag": "disabled",
            "x-platform-version": "window.navigator.userAgent"
        }
        data = {
            "page": 1,
            "perPage": 48,
            "filter": {"textQuery": name},
            "withBestProductReviews": False
        }
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.token_url, headers=headers, json=data) as response:
                content = await response.json()
        return content
    
    async def parse(self, name):
        if self.perekrestok_token == '':
            self.perekrestok_token = await self.get_token()
        content = await self.get_data(self.perekrestok_token, name)
        if content['content'] is None and content['error']['code'] == 'ACCESS_TOKEN_EXPIRED':
            self.perekrestok_token = await self.get_token()
            content = await self.get_data(self.perekrestok_token, name)
        items = [{
            "name": item['title'],
            "store_name": "Перекресток",
            "image_url": item['image']['cropUrlTemplate'] % ('400x400'),
            "actionDate": "",
            "discountPercent": item['priceTag']['labels'][0]['text'] if item['priceTag'].get('grossPrice') else "",
            "discount": True if item['priceTag'].get('grossPrice') else False,
            "price": str(item['priceTag']['price'] / 100).replace('.', ','),
            "oldprice": str(item['priceTag']['grossPrice'] / 100).replace('.', ',') if item['priceTag'].get('grossPrice') else None
        } for item in content['content']['items']]
        return items

@app.get("/search/{text}")
async def search(text):
    async def safe_call(api_call):
        try:
            return await api_call
        except Exception as e:
            print(f"Error during API call: {e}")
            return []
    perekrestok = PerekrestokAPI()
    one = time()
    results = await asyncio.gather(safe_call(magnitAPI(text)),
                                   safe_call(perekrestok.parse(text)),
                                   safe_call(ashanAPI(text)))
                                   
    print(time()-one)
    final_result_1 = {}
    final_result = [item for sublist in results if sublist for item in sublist]
    final_result_1['result'] = final_result 
    return JSONResponse(final_result_1)

@app.get("/magnit/{text}")
async def magnit(text):
    result = await magnitAPI(text)
    result_1 = {}
    result_1['result'] = result 
    return JSONResponse(result_1)

@app.get("/lenta/{text}")
async def lenta(text):
    result = await lentaAPI(text)
    result_1 = {}
    result_1['result'] = result 
    return JSONResponse(result_1)

@app.get("/perekrestok/{text}")
async def magnit(text):
    perekrestok = PerekrestokAPI()
    result = await perekrestok.parse(text)
    result_1 = {}
    result_1['result'] = result 
    return JSONResponse(result_1)

@app.get("/ashan/{text}")
async def ashat(text):
    result = await ashanAPI(text)
    result_1 = {}
    result_1['result'] = result 
    return JSONResponse(result_1)