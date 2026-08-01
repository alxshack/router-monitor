import sqlite3
import datetime

DB_NAME = 'router_monitor.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
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
    conn.close()

def insert_ping(success, latency=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    c.execute('INSERT INTO pings (timestamp, success, latency) VALUES (?, ?, ?)',
              (now, 1 if success else 0, latency))
    conn.commit()
    conn.close()

def cleanup_old_data(keep_days=365):
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=keep_days)).isoformat()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('DELETE FROM pings WHERE timestamp < ?', (cutoff,))
    conn.commit()
    conn.close()

def get_recent(limit=100):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT timestamp, success, latency FROM pings ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT COUNT(*), SUM(success) FROM pings')
    total, success_sum = c.fetchone()
    if total is None or total == 0:
        return {'total': 0, 'success': 0, 'fail': 0, 'percent': 0}
    fail = total - (success_sum or 0)
    percent = (success_sum / total * 100) if total else 0
    conn.close()
    return {
        'total': total,
        'success': success_sum or 0,
        'fail': fail,
        'percent': round(percent, 2)
    }

def get_day_data(date_str, offset_hours=4, current_time=None):
    """
    Возвращает список завершённых 10-минутных интервалов за указанную дату.
    Каждый элемент: {'time': 'HH:MM', 'status': 1 (доступен), 0 (недоступен), None (нет данных)}
    Обрезается по current_time (локальное время, datetime.time).
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Переводим локальный день в UTC интервал
    dt_local_start = datetime.datetime.strptime(date_str, '%Y-%m-%d')
    dt_local_end = dt_local_start + datetime.timedelta(days=1)
    dt_utc_start = dt_local_start - datetime.timedelta(hours=offset_hours)
    dt_utc_end = dt_local_end - datetime.timedelta(hours=offset_hours)
    start_str = dt_utc_start.isoformat()
    end_str = dt_utc_end.isoformat()
    c.execute('SELECT timestamp, success FROM pings WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC',
              (start_str, end_str))
    rows = c.fetchall()
    conn.close()

    # Инициализируем 144 интервала (ok, total)
    intervals = [[0, 0] for _ in range(144)]
    for ts, success in rows:
        dt_utc = datetime.datetime.fromisoformat(ts)
        dt_local = dt_utc + datetime.timedelta(hours=offset_hours)
        hour = dt_local.hour
        minute = dt_local.minute
        idx = hour * 6 + minute // 10
        intervals[idx][1] += 1
        if success == 1:
            intervals[idx][0] += 1

    # Определяем, сколько интервалов уже завершено
    if current_time is None:
        # Если не передано, берём текущее локальное время
        current_time = datetime.datetime.now() + datetime.timedelta(hours=offset_hours)
        current_time = current_time.time()
    # Вычисляем индекс последнего завершённого интервала
    # Интервал завершён, если его конец <= current_time
    # Конец интервала: (hour, minute+10) или следующий час
    max_idx = -1
    for idx in range(144):
        hour = idx // 6
        minute = (idx % 6) * 10
        # Время окончания интервала
        end_hour = hour
        end_minute = minute + 10
        if end_minute >= 60:
            end_hour += 1
            end_minute -= 60
        # Если конец интервала <= текущее время, он завершён
        if (end_hour < current_time.hour) or (end_hour == current_time.hour and end_minute <= current_time.minute):
            max_idx = idx
        else:
            break

    result = []
    for idx in range(max_idx + 1):
        hour = idx // 6
        minute = (idx % 6) * 10
        time_str = f"{hour:02d}:{minute:02d}"
        ok, total = intervals[idx]
        if total == 0:
            status = None  # нет данных
        else:
            status = 1 if ok == total else 0  # все успешны -> 1, иначе 0
        result.append({'time': time_str, 'status': status})
    return result