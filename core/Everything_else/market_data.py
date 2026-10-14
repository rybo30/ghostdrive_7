# [market_data.py]
import requests

def get_crypto_prices():
    """
    Pings CoinGecko for current BTC and ETH prices.
    No API key required for this basic public ping.
    """
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd"
    try:
        # 5 second timeout to prevent the UI from freezing if the web is slow
        response = requests.get(url, timeout=5)
        data = response.json()
        
        return {
            "BTC": data['bitcoin']['usd'],
            "ETH": data['ethereum']['usd']
        }
    except Exception as e:
        print(f"[MARKET ERROR] {e}")
        return None