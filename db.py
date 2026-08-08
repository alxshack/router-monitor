import sqlite3
import datetime
import os

DB_NAME = os.environ.get('ROUTER_MONITOR_DB', 'router_monitor.db')
TIMEZONE_OFFSET = int(os.environ.get('TIMEZONE_OFFSET', 3))

def _now_utc():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat()

def init_db():
    conn = sqlite3.connect(DB_NAME)
    try:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS pings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                success INTEGER NOT NULL,
                latency REAL
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON pings(timestamp)')
        conn.commit()
    finally:
        conn.close()

def insert_ping(success, latency=None):
    conn = sqlite3.connect(DB_NAME)
    try:
        c = conn.cursor()
        c.execute('INSERT INTO pings (timestamp, success, latency) VALUES (?, ?, ?)',
                  (_now_utc(), 1 if success else 0, latency))
        conn.commit()
    finally:
        conn.close()

def get_recent(limit=100):
    conn = sqlite3.connect(DB_NAME)
    try:
        c = conn.cursor()
        c.execute('SELECT timestamp, success, latency FROM pings ORDER BY timestamp DESC LIMIT ?', (limit,))
        return c.fetchall()
    finally:
        conn.close()

def get_day_data(date_str):
    """
    Возвращает все 144 десятиминутных интервала локального дня 00:00-24:00.
    Каждый элемент: {'time': 'HH:MM', 'status': 1 (доступен), 0 (недоступен), None (нет данных)}.
    """
    conn = sqlite3.connect(DB_NAME)
    try:
        c = conn.cursor()
        dt_local_start = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        dt_local_end = dt_local_start + datetime.timedelta(days=1)
        dt_utc_start = dt_local_start - datetime.timedelta(hours=TIMEZONE_OFFSET)
        dt_utc_end = dt_local_end - datetime.timedelta(hours=TIMEZONE_OFFSET)
        c.execute('SELECT timestamp, success FROM pings WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC',
                  (dt_utc_start.isoformat(), dt_utc_end.isoformat()))
        rows = c.fetchall()
    finally:
        conn.close()

    intervals = [[0, 0] for _ in range(144)]
    for ts, success in rows:
        dt_utc = datetime.datetime.fromisoformat(ts)
        dt_local = dt_utc + datetime.timedelta(hours=TIMEZONE_OFFSET)
        idx = dt_local.hour * 6 + dt_local.minute // 10
        intervals[idx][1] += 1
        if success == 1:
            intervals[idx][0] += 1

    result = []
    for idx in range(144):
        hour = idx // 6
        minute = (idx % 6) * 10
        ok, total = intervals[idx]
        if total == 0:
            status = None
        else:
            status = 1 if ok == total else 0
        result.append({'time': f'{hour:02d}:{minute:02d}', 'status': status})
    return result

def get_range_stats(start_date_str, end_date_str):
    """
    Агрегация по дням за период [start_date_str, end_date_str] (локальные даты).
    Каждый элемент: {'date': 'YYYY-MM-DD', 'percent': float|None, 'total': int}.
    Возвращаются все дни диапазона, включая дни без данных.
    """
    conn = sqlite3.connect(DB_NAME)
    try:
        c = conn.cursor()
        dt_local_start = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
        dt_local_end = datetime.datetime.strptime(end_date_str, '%Y-%m-%d') + datetime.timedelta(days=1)
        dt_utc_start = dt_local_start - datetime.timedelta(hours=TIMEZONE_OFFSET)
        dt_utc_end = dt_local_end - datetime.timedelta(hours=TIMEZONE_OFFSET)
        c.execute('SELECT timestamp, success FROM pings WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC',
                  (dt_utc_start.isoformat(), dt_utc_end.isoformat()))
        rows = c.fetchall()
    finally:
        conn.close()

    day_counts = {}
    for ts, success in rows:
        dt_utc = datetime.datetime.fromisoformat(ts)
        dt_local = dt_utc + datetime.timedelta(hours=TIMEZONE_OFFSET)
        day_key = dt_local.strftime('%Y-%m-%d')
        bucket = day_counts.setdefault(day_key, [0, 0])
        bucket[1] += 1
        if success == 1:
            bucket[0] += 1

    result = []
    cur = dt_local_start
    while cur.strftime('%Y-%m-%d') <= end_date_str:
        key = cur.strftime('%Y-%m-%d')
        ok, total = day_counts.get(key, (0, 0))
        if total == 0:
            percent = None
        else:
            percent = round(ok / total * 100, 1)
        result.append({'date': key, 'percent': percent, 'total': total})
        cur += datetime.timedelta(days=1)
    return result

def get_range_days(start_date_str, end_date_str):
    """
    Поинтервальные данные по каждому дню диапазона [start_date_str, end_date_str] (локальные даты).
    Каждый день: {'date': 'YYYY-MM-DD', 'intervals': [{'time': 'HH:MM', 'status': 1|0|None} x 144]}.
    """
    conn = sqlite3.connect(DB_NAME)
    try:
        c = conn.cursor()
        dt_local_start = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
        dt_local_end = datetime.datetime.strptime(end_date_str, '%Y-%m-%d') + datetime.timedelta(days=1)
        dt_utc_start = dt_local_start - datetime.timedelta(hours=TIMEZONE_OFFSET)
        dt_utc_end = dt_local_end - datetime.timedelta(hours=TIMEZONE_OFFSET)
        c.execute('SELECT timestamp, success FROM pings WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC',
                  (dt_utc_start.isoformat(), dt_utc_end.isoformat()))
        rows = c.fetchall()
    finally:
        conn.close()

    day_buckets = {}
    for ts, success in rows:
        dt_utc = datetime.datetime.fromisoformat(ts)
        dt_local = dt_utc + datetime.timedelta(hours=TIMEZONE_OFFSET)
        day_key = dt_local.strftime('%Y-%m-%d')
        idx = dt_local.hour * 6 + dt_local.minute // 10
        bucket = day_buckets.setdefault(day_key, [[0, 0] for _ in range(144)])
        bucket[idx][1] += 1
        if success == 1:
            bucket[idx][0] += 1

    result = []
    cur = dt_local_start
    while cur.strftime('%Y-%m-%d') <= end_date_str:
        key = cur.strftime('%Y-%m-%d')
        day_arr = day_buckets.get(key)
        intervals = []
        for idx in range(144):
            hour = idx // 6
            minute = (idx % 6) * 10
            if day_arr is None:
                status = None
            else:
                ok, total = day_arr[idx]
                status = None if total == 0 else (1 if ok == total else 0)
            intervals.append({'time': f'{hour:02d}:{minute:02d}', 'status': status})
        result.append({'date': key, 'intervals': intervals})
        cur += datetime.timedelta(days=1)
    return result
