from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import aiohttp
from json import loads, dumps
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from urllib.parse import unquote_plus
from time import time

# Дополнительные импорты для обработки цены
from sklearn.preprocessing import StandardScaler
from scipy.sparse import hstack, csr_matrix

app = FastAPI()
timeout = aiohttp.ClientTimeout(total=5)

searching_items = []

class RecommendationSystem:
    def __init__(self):
        self.clusters = []
        # Перед обработкой названий будет применяться функция synonym_replacer
        self.vectorizer = TfidfVectorizer(preprocessor=self.synonym_replacer)
        self.products = []  
        self.similarity_matrix = None
        self.combined_features = None
        self.price_scaler = None

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
        # Векторизация названий товаров после замены синонимов
        names = [self.synonym_replacer(p['name']) for p in self.products]
        name_features = self.vectorizer.fit_transform(names)
        
        # Обработка цены: преобразуем значение в число (учитывая возможные запятые)
        price_list = []
        for p in self.products:
            try:
                price_str = p['price']
                if isinstance(price_str, str):
                    price_str = price_str.replace(',', '.')
                price_val = float(price_str)
            except Exception as e:
                price_val = 0.0
            price_list.append([price_val])
        
        # Нормализуем цены с помощью StandardScaler
        scaler = StandardScaler()
        price_features = scaler.fit_transform(price_list)
        self.price_scaler = scaler  # сохраняем для последующей обработки запроса
        
        # Преобразуем числовой признак в разреженную матрицу и объединяем с вектором названия
        price_features_sparse = csr_matrix(price_features)
        combined_features = hstack([name_features, price_features_sparse])
        self.combined_features = combined_features
        
        # Пересчитываем матрицу сходства с учетом объединённых признаков
        self.similarity_matrix = cosine_similarity(combined_features)

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

    async def find_closest_cluster(self, product_name, product_price=None, exclude_products=None):
        if not self.products:
            raise HTTPException(status_code=404, detail="Нет доступных товаров для кластеризации")

        # Обработка названия и создание вектора TF-IDF
        processed_name = self.synonym_replacer(product_name)
        name_vector = self.vectorizer.transform([processed_name])
        
        # Обработка цены: если передана цена, преобразуем её, иначе по умолчанию 0.0
        if product_price is not None:
            try:
                price_val = float(str(product_price).replace(',', '.'))
            except:
                price_val = 0.0
        else:
            price_val = 0.0

        price_feature = self.price_scaler.transform([[price_val]])
        price_feature_sparse = csr_matrix(price_feature)
        
        # Формируем объединённый вектор признаков запроса
        query_vector = hstack([name_vector, price_feature_sparse])
        similarity_scores = cosine_similarity(query_vector, self.combined_features).flatten()
        
        closest_cluster = None
        max_similarity = 0
        for cluster in self.clusters:
            if not cluster:
                continue
            cluster_scores = []
            for prod in cluster:
                try:
                    idx = self.products.index(prod)
                    cluster_scores.append(similarity_scores[idx])
                except ValueError:
                    continue
            cluster_similarity = max(cluster_scores) if cluster_scores else 0
            if cluster_similarity > max_similarity:
                max_similarity = cluster_similarity
                closest_cluster = cluster
        
        if closest_cluster is None:
            return {"cluster": []}
        
        # Исключаем из результата те товары, которые были переданы в запросе
        if exclude_products:
            def product_match(p1, p2):
                try:
                    if p1.get("name") == p2.get("name") and p1.get("store_name") == p2.get("store_name"):
                        p1_price = float(str(p1.get("price")).replace(',', '.'))
                        p2_price = float(str(p2.get("price")).replace(',', '.'))
                        return abs(p1_price - p2_price) < 0.01
                    return False
                except Exception as e:
                    return False
            filtered_cluster = []
            for prod in closest_cluster:
                if not any(product_match(prod, ex) for ex in exclude_products):
                    filtered_cluster.append(prod)
            closest_cluster = filtered_cluster

        return {"cluster": closest_cluster}

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
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.main_url, headers=headers) as response:
                session_cookie = response.cookies.get("session")
        session_cookie = loads(unquote_plus(session_cookie.value))
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
            return []
    
    perekrestok = PerekrestokAPI()
    results = await asyncio.gather(safe_call(magnitAPI(text)),
                                   safe_call(perekrestok.parse(text)),
                                   safe_call(ashanAPI(text)))
    final_result = [item for sublist in results if sublist for item in sublist]
    if searching_items.count(text) < 50:
        searching_items.append(text)
    else:
        searching_items.append(text)
        searching_items.pop(0)
        
    # Формируем список продуктов для добавления в систему рекомендаций
    new_products = [{"name": item['name'], "price": item['price'], "store_name": item['store_name'], "image_url": item.get('image_url'), "oldprice": item.get('oldprice')} for item in final_result]
    await recommendation_system.add_new_products(new_products)
    return JSONResponse({"result": final_result})

@app.post("/cluster")
async def get_cluster(data: dict):
    if "products" in data.keys():
        info = data['products']
        result = []
        # Для каждого товара из входного списка ищем кластер с учетом его цены
        # и передаём весь список входных товаров для исключения их из результата
        for prod in info: 
            target_name = prod.get("name")
            target_price = prod.get("price")
            if not target_name:
                raise HTTPException(status_code=400, detail="Похожие товары не найдены, проверьте правильность отправленного типа данных!")
            cluster = await recommendation_system.find_closest_cluster(target_name, target_price, exclude_products=info)
            result.append(cluster)
        return JSONResponse({"result": result})
    else:
        target_name = data.get("name")
        target_price = data.get("price")
        if not target_name:
            raise HTTPException(status_code=400, detail="Похожие товары не найдены, проверьте правильность отправленного типа данных!")
        closest_cluster = await recommendation_system.find_closest_cluster(target_name, target_price)
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
