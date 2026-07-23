import os
import re
import json
import requests
 
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QDateEdit, QPushButton, QGroupBox, QPlainTextEdit, QMessageBox)
 
RASP_SEARCH_URL = "https://api.rasp.yandex.net/v3.0/search/"
RASP_STATIONS_URL = "https://api.rasp.yandex.net/v3.0/stations_list/"
RASP_KEY = "453f6770-09d4-40ad-8dbd-ad5eed9d4cda"
 
WEATHER_URL = "https://api.weather.yandex.ru/graphql/query"
WEATHER_KEY = "3bd62ff7-dd72-4952-9953-a29e60aadb94"
 
DISK_BASE = "https://cloud-api.yandex.net/v1/disk"
DISK_TOKEN = "y0__xDYh93EBxjblgMgp4yXxBaHAt92esd_LNS85F39oWXEcwTHJQ"
 
STATIONS_CACHE = "rasp_stations_list.json"
 
CITY_PRESETS = [
    "Москва", "Санкт-Петербург", "Тверь", "Торжок",
    "Архангельск", "Вологда", "Череповец", "Сыктывкар",
]
 
 
def iso_date(s):
    return (s or "")[:10]
 
 
def iso_time(s):
    if not s:
        return ""
    if "T" in s:
        return s.split("T", 1)[1][:8]
    return s[:8]
 
 
def dur_ru(seconds):
    if seconds is None:
        return ""
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    return f"{h}ч {m:02d}м"
 
 
def safe_filename(s):
    s = s.strip()
    s = re.sub(r'[<>:"/\\|?*\n\r\t]+', "_", s)
    return s or "trip"
 
 
def disk_upload_text(text, disk_path):
    headers = {"Authorization": "OAuth " + DISK_TOKEN}
 
    r = requests.get(
        DISK_BASE + "/resources/upload",
        headers=headers,
        params={"path": disk_path, "overwrite": "true"},
        timeout=20,
    )
    if r.status_code != 200:
        return False, r.status_code
 
    href = r.json().get("href")
    if not href:
        return False, r.status_code
 
    r2 = requests.put(href, data=text.encode("utf-8"), timeout=30)
    return (r2.status_code in (200, 201, 202)), r2.status_code
 
 
def coords_by_code(code):
    with open(STATIONS_CACHE, "r", encoding="utf-8") as f:
        data = json.load(f)
 
    for country in data.get("countries", []):
        for region in country.get("regions", []):
            for settlement in region.get("settlements", []):
                s_code = (settlement.get("codes") or {}).get("yandex_code")
 
                if s_code == code:
                    for st in settlement.get("stations") or []:
                        lat = st.get("latitude")
                        lon = st.get("longitude")
                        if lat is not None and lon is not None:
                            title = settlement.get("title") or st.get("title") or code
                            return title, float(lat), float(lon)
 
                for st in settlement.get("stations") or []:
                    st_code = (st.get("codes") or {}).get("yandex_code")
                    if st_code == code:
                        lat = st.get("latitude")
                        lon = st.get("longitude")
                        if lat is not None and lon is not None:
                            title = st.get("title") or code
                            return title, float(lat), float(lon)
 
    return None
 
 
def ensure_stations_cache(status_cb):
    if os.path.exists(STATIONS_CACHE) and os.path.getsize(STATIONS_CACHE) > 1024 * 1024:
        return
 
    status_cb("Скачиваю stations_list")
    r = requests.get(
        RASP_STATIONS_URL,
        params={"apikey": RASP_KEY, "format": "json", "lang": "ru_RU"},
        stream=True,
        timeout=120,
    )
    r.raise_for_status()
    with open(STATIONS_CACHE, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 128):
            if chunk:
                f.write(chunk)
 
 
def build_place_index():
    with open(STATIONS_CACHE, "r", encoding="utf-8") as f:
        data = json.load(f)
 
    items = []
    m = {}
 
    def add(title, code):
        if not title or not code:
            return
        k = title.strip().lower()
        if not k:
            return
        if k not in m:
            m[k] = (code, title.strip())
            items.append((k, title.strip(), code))
 
    for country in data.get("countries", []):
        for region in country.get("regions", []):
            for settlement in region.get("settlements", []):
                st_title = settlement.get("title") or ""
                st_code = (settlement.get("codes") or {}).get("yandex_code")
                add(st_title, st_code)
 
                for st in settlement.get("stations") or []:
                    t = st.get("title") or ""
                    c = (st.get("codes") or {}).get("yandex_code")
                    add(t, c)
 
    return m, items
 
 
def resolve_place(text, idx_map, idx_items):
    s = (text or "").strip()
    if not s:
        return None
 
    if re.fullmatch(r"[cs]\d+", s, flags=re.IGNORECASE):
        return s, s
 
    k = s.lower()
    if k in idx_map:
        return idx_map[k][0], idx_map[k][1]
 
    best = None
    best_len = None
    for kk, title, code in idx_items:
        if k in kk:
            ln = len(title)
            if best is None or ln < best_len:
                best = (code, title)
                best_len = ln
                if ln <= len(s) + 2:
                    break
    return best
 
 
def rasp_search(from_code, to_code, date_s):
    segments = []
    offset = 0
    limit = 100
 
    while True:
        params = {
            "apikey": RASP_KEY,
            "format": "json",
            "lang": "ru_RU",
            "from": from_code,
            "to": to_code,
            "date": date_s,
            "limit": limit,
            "offset": offset,
        }
        r = requests.get(RASP_SEARCH_URL, params=params, timeout=30)
        if r.status_code != 200:
            try:
                t = (r.json().get("error") or {}).get("text")
                if t:
                    raise RuntimeError(t)
            except Exception:
                pass
            raise RuntimeError(str(r.status_code))
 
        j = r.json()
        segments.extend(j.get("segments") or [])
 
        pag = j.get("pagination") or {}
        total = pag.get("total")
        if total is None:
            break
 
        offset += limit
        if offset >= total:
            break
 
    segments.sort(key=lambda x: (x.get("departure") or ""))
    return segments
 
 
def weather_now(lat, lon):
    headers = {"X-Yandex-Weather-Key": WEATHER_KEY}
    query = f"""
{{
  weatherByPoint(request: {{ lat: {lat}, lon: {lon} }}) {{
    now {{
      temperature
      condition
      precType
    }}
    forecast {{
      days(limit: 15) {{
        time
        parts {{
          day {{ avgTemperature }}
          night {{ avgTemperature }}
        }}
      }}
    }}
  }}
}}
""".strip()
 
    r = requests.post(WEATHER_URL, headers=headers, json={"query": query}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(str(data["errors"]))
 
    w = (data.get("data") or {}).get("weatherByPoint") or {}
    return w
 
 
def weather_for_date(wobj, date_s):
    fc = (wobj.get("forecast") or {}).get("days") or []
    for d in fc:
        if iso_date(d.get("time")) == date_s:
            parts = d.get("parts") or {}
            day = (parts.get("day") or {}).get("avgTemperature")
            night = (parts.get("night") or {}).get("avgTemperature")
            if day is not None:
                return day, night
    return None, None
 
 
def has_precip(condition, prec_type):
    if prec_type and str(prec_type).upper() not in ("NONE", "0"):
        return True
    c = (condition or "").lower()
    dry = {"clear", "partly-cloudy", "cloudy", "overcast"}
    return (c not in dry) and bool(c)
 
 
class Worker(QObject):
    done = pyqtSignal(dict)
    status = pyqtSignal(str)
    fail = pyqtSignal(str)
 
    def __init__(self, from_text, to_text, date_s):
        super().__init__()
        self.from_text = from_text
        self.to_text = to_text
        self.date_s = date_s
 
    def run(self):
        try:
            self.status.emit("Подготовка справочника...")
            ensure_stations_cache(lambda m: self.status.emit(m))
            idx_map, idx_items = build_place_index()
 
            a = resolve_place(self.from_text, idx_map, idx_items)
            b = resolve_place(self.to_text, idx_map, idx_items)
            if not a or not b:
                raise RuntimeError("Не смог распознать пункт(ы). Введи код (c/s...) или точное название.")
 
            from_code, from_title = a
            to_code, to_title = b
 
            self.status.emit("Запрашиваю расписание...")
            segs = rasp_search(from_code, to_code, self.date_s)
 
            arr_date = self.date_s
            if segs:
                arr_date = iso_date(segs[0].get("arrival")) or self.date_s
 
            self.status.emit("Запрашиваю погоду...")
            coords = coords_by_code(to_code)
            if coords:
                w_title, lat, lon = coords
                wobj = weather_now(lat, lon)
                now = wobj.get("now") or {}
                now_t = now.get("temperature")
                day_t, night_t = weather_for_date(wobj, arr_date)
                precip = "Да" if has_precip(now.get("condition"), now.get("precType")) else "Нет"
            else:
                w_title = to_title
                precip = "—"
 
            with open(STATIONS_CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
            found = False
            for country in data.get("countries", []):
                for region in country.get("regions", []):
                    for settlement in region.get("settlements", []):
                        for st in settlement.get("stations") or []:
                            if ((st.get("codes") or {}).get("yandex_code") == to_code):
                                lat = st.get("latitude")
                                lon = st.get("longitude")
                                w_title = st.get("title") or to_title
                                found = True
                                break
                        if found:
                            break
                    if found:
                        break
                if found:
                    break
 
            wobj = None
            day_t = None
            night_t = None
            now_t = None
            precip = None
 
            if lat is not None and lon is not None:
                wobj = weather_now(float(lat), float(lon))
                now = wobj.get("now") or {}
                now_t = now.get("temperature")
                day_t, night_t = weather_for_date(wobj, arr_date)
                precip = "Да" if has_precip(now.get("condition"), now.get("precType")) else "Нет"
            else:
                precip = "—"
 
            self.done.emit({
                "from_title": from_title,
                "to_title": to_title,
                "date": self.date_s,
                "arr_date": arr_date,
                "segments": segs,
                "weather_title": w_title,
                "now_t": now_t,
                "day_t": day_t,
                "night_t": night_t,
                "precip": precip,
            })
        except Exception as e:
            self.fail.emit(str(e))
 
 
class TravelWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Путешествие")
 
        self.last_report = ""
        self.last_fname = "trip.txt"
 
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
 
        top = QVBoxLayout()
 
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Откуда:"))
        self.cb_from = QComboBox()
        self.cb_from.setEditable(True)
        self.cb_from.addItems(CITY_PRESETS)
        self.cb_from.setMinimumWidth(260)
        r1.addWidget(self.cb_from)
 
        r1.addWidget(QLabel("Куда:"))
        self.cb_to = QComboBox()
        self.cb_to.setEditable(True)
        self.cb_to.addItems(CITY_PRESETS)
        self.cb_to.setMinimumWidth(260)
        r1.addWidget(self.cb_to)
        top.addLayout(r1)
 
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Дата:"))
        self.de = QDateEdit()
        self.de.setCalendarPopup(True)
        self.de.setDisplayFormat("dd.MM.yyyy")
        self.de.setDate(QDate.currentDate())
        self.de.setMinimumWidth(140)
        r2.addWidget(self.de)
        r2.addStretch(1)
        top.addLayout(r2)
 
        r3 = QHBoxLayout()
        self.btn_show = QPushButton("Показать")
        self.btn_save = QPushButton("Сохранить")
        self.btn_save.setEnabled(False)
        self.btn_show.setMinimumHeight(32)
        self.btn_save.setMinimumHeight(32)
        r3.addWidget(self.btn_show)
        r3.addWidget(self.btn_save)
        top.addLayout(r3)
 
        main.addLayout(top)
 
        gb1 = QGroupBox("Расписание маршрутов")
        gb1_l = QVBoxLayout(gb1)
        self.schedule = QPlainTextEdit()
        self.schedule.setReadOnly(True)
        self.schedule.setFont(QFont("Consolas", 10))
        gb1_l.addWidget(self.schedule)
        main.addWidget(gb1)
 
        gb2 = QGroupBox("Погода в пункте назначения")
        gb2_l = QVBoxLayout(gb2)
        self.w_title = QLabel("")
        self.w_temp = QLabel("")
        self.w_prec = QLabel("")
        gb2_l.addWidget(self.w_title)
        gb2_l.addWidget(self.w_temp)
        gb2_l.addWidget(self.w_prec)
        main.addWidget(gb2)
 
        self.status = QLabel("")
        main.addWidget(self.status)
 
        self.btn_show.clicked.connect(self.on_show)
        self.btn_save.clicked.connect(self.on_save)
 
        self.thread = None
        self.worker = None
 
    def on_show(self):
        a = self.cb_from.currentText().strip()
        b = self.cb_to.currentText().strip()
        date_s = self.de.date().toString("yyyy-MM-dd")
 
        if not a or not b:
            QMessageBox.warning(self, "Ошибка", "Заполни 'Откуда' и 'Куда'.")
            return
 
        self.status.setText("")
        self.schedule.setPlainText("")
        self.w_title.setText("")
        self.w_temp.setText("")
        self.w_prec.setText("")
        self.btn_save.setEnabled(False)
        self.last_report = ""
 
        self.thread = QThread()
        self.worker = Worker(a, b, date_s)
        self.worker.moveToThread(self.thread)
 
        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self.status.setText)
        self.worker.done.connect(self.on_done)
        self.worker.fail.connect(self.on_fail)
        self.worker.done.connect(self.thread.quit)
        self.worker.fail.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
 
        self.thread.start()
 
    def on_done(self, res):
        segs = res["segments"]
        lines = []
        lines.append("Транспорт Номер Отпр. Приб. Время")
        for s in segs:
            th = s.get("thread") or {}
            tt = (th.get("transport_type") or "").lower()
            num = th.get("number") or ""
            if tt == "train":
                tname = "Поезд"
            elif tt == "plane":
                tname = "Самолет"
            elif tt == "bus":
                tname = "Автобус"
            elif tt == "suburban":
                tname = "Эл-ка"
            else:
                tname = tt or "—"
 
            dep = iso_time(s.get("departure"))
            arr = iso_time(s.get("arrival"))
            d = dur_ru(s.get("duration"))
            lines.append(f"{tname:<9}{num:<10}{dep:<10}{arr:<10}{d:>6}")
 
        self.schedule.setPlainText("\n".join(lines))
 
        wt = res["weather_title"]
        self.w_title.setText(f"<b>Погода в {wt}:</b>")
 
        date_note = res["arr_date"]
        if res["day_t"] is not None:
            self.w_temp.setText(f"Температура (днём/ночью, {date_note}): {res['day_t']}°C / {res['night_t']}°C")
        elif res["now_t"] is not None:
            self.w_temp.setText(f"Температура: {res['now_t']}°C")
        else:
            self.w_temp.setText("Температура: —")
 
        self.w_prec.setText(f"Осадки: {res['precip']}")
 
        self.last_fname = safe_filename(f"{res['from_title']}_{res['to_title']}_{res['date']}.txt")
        self.last_report = (
                f"Откуда: {res['from_title']}\n"
                f"Куда: {res['to_title']}\n"
                f"Дата: {res['date']}\n\n"
                + self.schedule.toPlainText()
                + "\n\n"
                + f"Погода в {wt}:\n"
                + self.w_temp.text().replace("<b>", "").replace("</b>", "") + "\n"
                + self.w_prec.text()
                + "\n"
        )
 
        self.btn_save.setEnabled(True)
        self.status.setText("Готово")
 
        self.push_combo_item(self.cb_from, res["from_title"])
        self.push_combo_item(self.cb_to, res["to_title"])
 
    def push_combo_item(self, cb, text):
        t = (text or "").strip()
        if not t:
            return
        for i in range(cb.count()):
            if cb.itemText(i).strip().lower() == t.lower():
                return
        cb.insertItem(0, t)
 
    def on_fail(self, msg):
        self.status.setText("Ошибка")
        QMessageBox.critical(self, "Ошибка", msg)
 
    def on_save(self):
        if not self.last_report:
            return
 
        remote = "disk:/trip/" + self.last_fname
        try:
            ok, code = disk_upload_text(self.last_report, remote)
            if ok:
                self.status.setText("Файл сохранен на Яндекс Диск")
                return
            local = os.path.abspath(self.last_fname)
            with open(local, "w", encoding="utf-8") as f:
                f.write(self.last_report)
            self.status.setText("Файл сохранен на компьютер")
        except Exception:
            local = os.path.abspath(self.last_fname)
            with open(local, "w", encoding="utf-8") as f:
                f.write(self.last_report)
            self.status.setText("Файл сохранен на компьютер")
 
 
if __name__ == "__main__":
    app = QApplication([])
    w = TravelWindow()
    w.resize(1100, 850)
    w.show()
    app.exec()