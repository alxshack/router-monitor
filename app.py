import datetime
import os
from flask import Flask, render_template, jsonify, request
from db import get_recent, get_day_data, get_range_days, TIMEZONE_OFFSET

app = Flask(__name__)

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

def now_local():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=TIMEZONE_OFFSET)

def compute_end_date(start_str, mode):
    start = datetime.datetime.strptime(start_str, '%Y-%m-%d')
    if mode == 'week':
        end = start + datetime.timedelta(days=6)
    elif mode == 'month':
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1, day=1) - datetime.timedelta(days=1)
        else:
            end = start.replace(month=start.month + 1, day=1) - datetime.timedelta(days=1)
    else:
        end = start
    return end.strftime('%Y-%m-%d')

@app.route('/')
def index():
    last_row = get_recent(1)
    last_status = None
    last_time = None
    if last_row:
        ts, success, _ = last_row[0]
        last_status = 'Доступен' if success else 'Недоступен'
        last_time = format_datetime(ts)
    return render_template('index.html',
                           last_status=last_status,
                           last_time=last_time)

@app.route('/api/range')
def api_range():
    date_str = request.args.get('start')
    if not date_str:
        date_str = now_local().strftime('%Y-%m-%d')
    mode = request.args.get('mode', 'day')
    end_date = compute_end_date(date_str, mode)
    if mode == 'day':
        data = get_day_data(date_str)
        payload = {'intervals': data}
    else:
        data = get_range_days(date_str, end_date)
        payload = {'days': data}
    return jsonify({
        'start': date_str,
        'end': end_date,
        'mode': mode,
        **payload,
        'now': now_local().isoformat()
    })

@app.route('/api/status')
def api_status():
    last_row = get_recent(1)
    last = None
    if last_row:
        ts, success, latency = last_row[0]
        last = {
            'timestamp': ts,
            'success': bool(success),
            'latency': latency
        }
    return jsonify({'last': last})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
