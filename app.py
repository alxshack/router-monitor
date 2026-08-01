from flask import Flask, render_template, jsonify, request
from db import get_stats, get_day_data, get_recent
import datetime
import sqlite3

app = Flask(__name__)
DB_NAME = 'router_monitor.db'
TIMEZONE_OFFSET = 3   # UTC+3

def localize(dt):
    return dt + datetime.timedelta(hours=TIMEZONE_OFFSET)

def format_datetime(iso_str):
    if iso_str is None:
        return 'сейчас'
    dt = datetime.datetime.fromisoformat(iso_str)
    dt_local = localize(dt)
    months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
              'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
    return f"{dt_local.day} {months[dt_local.month-1]} {dt_local.year} ({dt_local.hour:02d}:{dt_local.minute:02d})"

def get_periods():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('SELECT timestamp, success FROM pings ORDER BY timestamp ASC')
    rows = c.fetchall()
    conn.close()
    if not rows:
        return []
    periods = []
    current_start = rows[0][0]
    current_status = rows[0][1]
    for ts, success in rows[1:]:
        if success != current_status:
            periods.append({
                'start': current_start,
                'end': ts,
                'status': 'Доступен' if current_status else 'Недоступен'
            })
            current_start = ts
            current_status = success
    periods.append({
        'start': current_start,
        'end': None,
        'status': 'Доступен' if current_status else 'Недоступен'
    })
    return periods

@app.route('/')
def index():
    stats = get_stats()
    periods = get_periods()
    periods_display = []
    for p in periods:
        periods_display.append({
            'start': format_datetime(p['start']),
            'end': format_datetime(p['end']) if p['end'] else 'сейчас',
            'status': p['status']
        })
    # Получаем последнюю запись
    last_row = get_recent(1)
    last_status = None
    last_time = None
    if last_row:
        ts, success, _ = last_row[0]
        last_status = 'Доступен' if success else 'Недоступен'
        last_time = format_datetime(ts)
    return render_template('index.html',
                           stats=stats,
                           periods=periods_display,
                           last_status=last_status,
                           last_time=last_time)

@app.route('/api/day')
def api_day():
    date_str = request.args.get('date')
    if not date_str:
        now_local = datetime.datetime.now() + datetime.timedelta(hours=TIMEZONE_OFFSET)
        date_str = now_local.strftime('%Y-%m-%d')
    # Передаём текущее локальное время для обрезки
    current_local = datetime.datetime.now() + datetime.timedelta(hours=TIMEZONE_OFFSET)
    data = get_day_data(date_str, offset_hours=TIMEZONE_OFFSET, current_time=current_local.time())
    return jsonify({
        'date': date_str,
        'intervals': data   # список словарей {time, status}
    })

@app.route('/api/data')
def api_data():
    rows = get_recent(500)
    data = [{'timestamp': ts, 'success': success, 'latency': latency} for ts, success, latency in rows]
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)