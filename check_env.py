from decouple import config

api_key = config('NEWSAPI_KEY')
print(f"Ваш ключ NewsAPI: {api_key}")
