from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
from json import loads
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from urllib.parse import unquote_plus
from json import dumps

import asyncio
import aiohttp
from time import time

app = FastAPI()

timeout = aiohttp.ClientTimeout(total=5)
app = FastAPI()

class RecommendationSystem:
    def __init__(self):
        self.clusters = []
        self.vectorizer = TfidfVectorizer(preprocessor=self.synonym_replacer)
        self.products = []  
        self.similarity_matrix = None

    def synonym_replacer(self, text):
        synonyms = {
            "кола": "cola",
            "Cola": "cola",
            "cola": "cola",

        }
        for word, replacement in synonyms.items():
            text = text.replace(word, replacement)
        return text

    def preprocess_products(self):
        # Используем только название для векторизации
        X = self.vectorizer.fit_transform([p['name'] for p in self.products])
        self.similarity_matrix = cosine_similarity(X)

    def cluster_products(self, threshold=0.55):
        visited = set()
        self.clusters.clear()
        for i in range(len(self.products)):
            if i in visited:
                continue
            cluster = [self.products[i]]
            visited.add(i)
            for j in range(i + 1, len(self.products)):
                if self.similarity_matrix[i][j] > threshold:
                    cluster.append(self.products[j])
                    visited.add(j)
            self.clusters.append(cluster)

    async def add_new_products(self, new_products):
        added = False
        for product in new_products:
            if product not in self.products:
                self.products.append(product)
                added = True
        if added:
            self.preprocess_products()
            self.cluster_products()

    async def find_closest_cluster(self, product_name):
        if not self.products:
            raise HTTPException(status_code=404, detail="Нет доступных товаров для кластеризации")

        vector = self.vectorizer.transform([self.synonym_replacer(product_name)])
        similarity_scores = cosine_similarity(vector, self.vectorizer.transform([p['name'] for p in self.products])).flatten()

        closest_cluster = None
        max_similarity = 0
        for cluster in self.clusters:
            cluster_similarity = max([similarity_scores[self.products.index(prod)] for prod in cluster])
            if cluster_similarity > max_similarity:
                max_similarity = cluster_similarity
                closest_cluster = cluster

        if closest_cluster:
            return {"cluster": closest_cluster}
        else:
            return {"cluster": []}

recommendation_system = RecommendationSystem()

async def ashanAPI(text):
    params = {
        'apiKey': '06U4652632',
        'strategy': 'advanced_xname,zero_queries',
        'fullData': 'true',
        'withCorrection': 'true',
        'withFacets': 'true',
        'treeFacets': 'true',
        'regionId': '1',
        'useCategoryPrediction': '0.2',
        'preview': 'false',
        'withSku': 'false',
        'sort': 'DEFAULT'
    }
    params["st"] = text
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get('https://sort.diginetica.net/search', params=params) as response:
            products = await response.json()
    items = [{
        "name": item['name'],
        "store_name": "Ашан",
        "image_url": item['image_url'],
        "actionDate": "",
        "discountPercent": f"-{round(100 - float(item['price']) * 100 / float(item['oldPrice']))}%" if item.get('oldPrice') else None,
        "discount": True if item.get('oldPrice') else False,
        "price": item['price'],
        "oldprice": item.get('oldPrice')
    } for item in products['products']]
    return items

async def magnitAPI(name):
    headers = {
        'host': 'magnit.ru',
        'x-device-tag': 'disabled',
        'x-platform-version': 'Windows Chrome 127',
        'x-app-version': '7.0.0',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'content-type': 'application/json',
        'accept': 'application/json',
        'x-device-platform': 'Web',
        'x-client-name': 'magnit',
        'x-device-id': '1A5D0A5D-8C76-CEC4-D837-622100832565'
    }
    params = {"includeForAdults": True, "term": name, "pagination": {"offset": 0, "limit": 6}, "sort": {"order": "desc", "type": "popularity"}, "storeCode": "559060", "storeType": "1", "catalogType": "1"}
    headers['Content-Length'] = str(len(dumps(params)))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post('https://magnit.ru/webgate/v2/goods/search', headers=headers, json=params) as response:
            data = await response.json()
    items = [{
        "name": item['name'],
        "store_name": "Магнит",
        "image_url": item["gallery"][0]['url'],
        "actionDate": "",
        "discountPercent": f"-{round(100 - float(item['price']) * 100 / float(item['promotion']['oldPrice']))}%" if item['promotion'].get('oldPrice') else None,
        "discount": True if item['promotion'].get('oldPrice') else False,
        "price": item['price'] / 100,
        "oldprice": item['promotion']['oldPrice'] / 100 if item['promotion'].get('oldPrice') else None,
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
async def search(text: str):
    async def safe_call(api_call):
        try:
            return await api_call
        except Exception as e:
            print(f"Error during API call: {e}")
            return []

    # Выполняем поиск в различных API
    perekrestok = PerekrestokAPI()
    one = time()
    results = await asyncio.gather(safe_call(magnitAPI(text)),
                                   safe_call(perekrestok.parse(text)),
                                   safe_call(ashanAPI(text)))

    final_result = [item for sublist in results if sublist for item in sublist]

    # Извлекаем названия продуктов для добавления в кластер
    new_products = [{"name": item['name'], "price": item['price'], "store_name": item['store_name'], "image_url": item['image_url'], 'oldprice':item['oldprice']} for item in final_result]

    # Добавляем новые продукты в систему рекомендаций
    await recommendation_system.add_new_products(new_products)

    final_result_1 = {'result': final_result}
    print(time() - one)

    return JSONResponse(final_result_1)

@app.post("/cluster")
async def get_cluster(data: dict):
    if "products" in data.keys():
        info = data['products']
        result = []
        final_result = {}
        for i in info: 
            target_product = i.get("target_product")

            

            if not target_product:
                raise HTTPException(status_code=400, detail="Похожие товары не найдены, проверьте правильность отправленного типа данных!")

            
            closest_cluster = await recommendation_system.find_closest_cluster(target_product)
            result.append(closest_cluster)
        final_result['result'] = result
        return JSONResponse(final_result,)
    else:
        target_product = data.get("target_product")

        

        if not target_product:
            raise HTTPException(status_code=400, detail="Похожие товары не найдены, проверьте правильность отправленного типа данных!")

        closest_cluster = await recommendation_system.find_closest_cluster(target_product)

        return JSONResponse(closest_cluster)

@app.get("/magnit/{text}")
async def magnit(text: str):
    result = await magnitAPI(text)
    new_products = [{"name": item['name'], "price": item['price']} for item in result]
    await recommendation_system.add_new_products(new_products)
    return JSONResponse({"result": result})

@app.get("/perekrestok/{text}")
async def perekrestok(text: str):
    perekrestok = PerekrestokAPI()
    result = await perekrestok.parse(text)
    new_products = [{"name": item['name'], "price": item['price']} for item in result]
    await recommendation_system.add_new_products(new_products)
    return JSONResponse({"result": result})

@app.get("/ashan/{text}")
async def ashan(text: str):
    result = await ashanAPI(text)
    new_products = [{"name": item['name'], "price": item['price']} for item in result]
    await recommendation_system.add_new_products(new_products)
    return JSONResponse({"result": result})
