import time
import sys
import os
import traceback
import sqlite3
import requests
import urllib3
from db import init_db, insert_ping, DB_NAME as DB_FILE

# Самоподписанный сертификат роутера: подавляем предупреждение urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Укажите ваш домен KeenDNS (без http://, только имя)
ROUTER_DOMAIN = os.environ.get('ROUTER_DOMAIN', 'tihultra.netcraze.pro')
# Используйте HTTPS, если админка доступна по HTTPS
ROUTER_URL = f'https://{ROUTER_DOMAIN}'
TIMEOUT = float(os.environ.get('CHECK_TIMEOUT', 5))  # секунд
INTERVAL = int(os.environ.get('CHECK_INTERVAL', 600))  # 10 минут
CHECK_ATTEMPTS = int(os.environ.get('CHECK_ATTEMPTS', 3))
CHECK_RETRY_DELAY = int(os.environ.get('CHECK_RETRY_DELAY', 10))  # секунд между попытками

def check_web(url):
    """Проверяет доступность веб-интерфейса по HTTP(S)."""
    try:
        start = time.time()
        # Если сертификат самоподписанный, можно отключить проверку verify=False,
        # но лучше добавить сертификат в доверенные.
        response = requests.get(url, timeout=TIMEOUT, allow_redirects=True, verify=False)
        latency = (time.time() - start) * 1000
        # Успехом считаем любой ответ ниже 400 (включая редиректы/логин-страницы)
        success = response.status_code < 400
        return success, latency
    except requests.exceptions.RequestException as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return False, None

def check_web_with_retry(url):
    """Проверяет доступность до CHECK_ATTEMPTS раз с паузой между попытками.
    Возвращает (success, latency, attempts). Недоступен — только после всех отказов."""
    for attempt in range(1, CHECK_ATTEMPTS + 1):
        success, latency = check_web(url)
        if success:
            return True, latency, attempt
        if attempt < CHECK_ATTEMPTS:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - attempt {attempt}/{CHECK_ATTEMPTS} failed, "
                  f"retrying in {CHECK_RETRY_DELAY}s", file=sys.stderr)
            time.sleep(CHECK_RETRY_DELAY)
    return False, None, CHECK_ATTEMPTS

def main():
    try:
        init_db()
    except sqlite3.OperationalError as e:
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - DB error at init: {e}\n"
              f"Проверьте права на {DB_FILE}: chown/chmod должен разрешать запись", file=sys.stderr)
    print(f"Service started. Checking {ROUTER_URL} every {INTERVAL}s "
          f"(attempts: {CHECK_ATTEMPTS}, retry delay: {CHECK_RETRY_DELAY}s)")
    while True:
        try:
            success, latency, attempts = check_web_with_retry(ROUTER_URL)
            insert_ping(success, latency)
            status = "UP" if success else "DOWN"
            suffix = f" (latency: {latency:.2f}ms)" if latency is not None else ""
            if attempts > 1:
                suffix += f" (attempts: {attempts})"
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {status}{suffix}")
        except sqlite3.OperationalError as e:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - DB error: {e}\n"
                  f"Проверьте права на {DB_FILE}: chown/chmod должен разрешать запись", file=sys.stderr)
        except Exception:
            print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - unexpected error:\n"
                  f"{traceback.format_exc()}", file=sys.stderr)
        time.sleep(INTERVAL)

if __name__ == '__main__':
    main()
