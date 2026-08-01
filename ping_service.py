import time
import sys
import requests
from db import init_db, insert_ping, cleanup_old_data

# Укажите ваш домен KeenDNS (без http://, только имя)
ROUTER_DOMAIN = 'tihultra.netcraze.pro'   # замените на ваше имя
# Используйте HTTPS, если админка доступна по HTTPS
ROUTER_URL = f'https://{ROUTER_DOMAIN}'
TIMEOUT = 5  # секунд
INTERVAL = 600  # 10 минут

def check_web(url):
    """Проверяет доступность веб-интерфейса по HTTP(S)."""
    try:
        start = time.time()
        # Если сертификат самоподписанный, можно отключить проверку verify=False,
        # но лучше добавить сертификат в доверенные.
        response = requests.get(url, timeout=TIMEOUT, allow_redirects=True, verify=False)
        latency = (time.time() - start) * 1000
        # Считаем успехом, если статус-код 200 (или хотя бы < 400)
        success = response.status_code == 200
        return success, latency
    except requests.exceptions.RequestException as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return False, None

def main():
    init_db()
    print(f"Service started. Checking {ROUTER_URL} every {INTERVAL}s")
    last_cleanup = 0
    while True:
        if time.time() - last_cleanup >= 24 * 3600:
            cleanup_old_data()
            last_cleanup = time.time()
        success, latency = check_web(ROUTER_URL)
        insert_ping(success, latency)
        status = "UP" if success else "DOWN"
        if latency is not None:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {status} (latency: {latency:.2f}ms)")
        else:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {status}")
        time.sleep(INTERVAL)

if __name__ == '__main__':
    main()