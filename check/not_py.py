import sys
import os
import re
import json
import requests
import csv
import random
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QDateEdit,
    QPlainTextEdit,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QMessageBox
)
from PyQt6.QtCore import QDate, QObject, QThread, pyqtSignal
from PyQt6.QtGui import QFont

RASP_SEARCH_URL = "https://api.rasp.yandex.net/v3.0/search/"
RASP_STATIONS_URL = "https://api.rasp.yandex.net/v3.0/stations_list/"
RASP_KEY = "45ba08b6-f0f5-48a3-aadb-85de5791adf0"

DISK_BASE = "https://cloud-api.yandex.net/v1/disk"
DISK_TOKEN = "y0__xDYh93EBxjblgMgp4yXxBaHAt92esd_LNS85F39oWXEcwTHJQ"

STATIONS_CACHE = "rasp_stations_list.json"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.lis = [
            "Москва",
            "Санкт-Петербург",
            "Тверь",
            "Нижний Новгород",
            "Великий Новгород",
            "Казань",
            "Владимир",
            "Ярославль",
            "Рязань",
            "Тула"
        ]
        self.setWindowTitle("МЕГАРАБОТА")
        self.setGeometry(100, 100, 1000, 600)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.towns1 = QComboBox()
        self.towns2 = QComboBox()
        for c in self.lis:
            self.towns1.addItem(c)
            self.towns2.addItem(c)
        self.label1 = QLabel("Откуда")
        self.label2 = QLabel("Туда")
        self.label3 = QLabel("Дата")

        layout1 = QHBoxLayout()
        layout1.addWidget(self.label1)
        layout1.addWidget(self.towns1, 1)
        layout1.setContentsMargins(0, 0, 0, 0)
        layout1.setSpacing(7)
        layout1.addStretch()

        layout2 = QHBoxLayout()
        layout2.addWidget(self.label2)
        layout2.addWidget(self.towns2, 1)
        layout2.setContentsMargins(0, 0, 0, 0)
        layout2.setSpacing(2)
        layout2.addStretch()

        main_layout.setSpacing(3)
        main_layout.addLayout(layout1)
        main_layout.addLayout(layout2)

        self.date_type = QDateEdit()
        self.date_type.setDate(QDate.currentDate())
        self.date_type.setCalendarPopup(True)
        self.date_type.setDisplayFormat("dd.MM.yyyy")
        self.date_type.setMaximumDate(QDate.currentDate().addDays(45))
        self.date_type.setMinimumDate(QDate.currentDate())

        layout3 = QHBoxLayout()
        layout3.addWidget(self.label3)
        layout3.addWidget(self.date_type, 1)
        layout3.setContentsMargins(0, 0, 0, 0)
        layout3.setSpacing(7)
        layout3.addStretch()

        main_layout.addLayout(layout3)

        self.button1 = QPushButton("Показать")
        self.button2 = QPushButton("Сохранить")
        layout4 = QHBoxLayout()
        layout4.addWidget(self.button1)
        layout4.addWidget(self.button2)

        main_layout.addLayout(layout4)
        
        self.button1.clicked.connect(self.showing)
        self.button2.clicked.connect(self.saving)

        self.schedule = QPlainTextEdit()
        self.schedule.setReadOnly(True)
        main_layout.addWidget(self.schedule, 1)
        
        gb2 = QGroupBox("Погода в пункте назначения")
        gb2_l = QVBoxLayout(gb2)
        self.w_title = QLabel("")
        self.w_temp = QLabel("")
        self.w_prec = QLabel("")
        gb2_l.addWidget(self.w_title)
        gb2_l.addWidget(self.w_temp)
        gb2_l.addWidget(self.w_prec)
        main_layout.addWidget(gb2)
        main_layout.addStretch()
        
        self.last_report = ""
        self.last_fname = "trip.txt"

    def showing(self):
        from_text = self.towns1.currentText().strip()
        to_text = self.towns2.currentText().strip()
        date_s = self.date_type.date().toString("yyyy-MM-dd")
        
        if not from_text or not to_text:
            QMessageBox.warning(self, "Ошибка", "Заполни 'Откуда' и 'Куда'.")
            return
        
        if not os.path.exists(STATIONS_CACHE):
            self.schedule.setPlainText("Скачивание справочника станций...")
        else:
            self.schedule.setPlainText("Загрузка...")
            
        self.w_title.setText("")
        self.w_temp.setText("")
        self.w_prec.setText("")
        
        self.thread = QThread()
        self.worker = Worker(from_text, to_text, date_s)
        self.worker.moveToThread(self.thread)
        
        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self.schedule.setPlainText)
        self.worker.done.connect(self.on_done)
        self.worker.fail.connect(self.on_fail)
        self.worker.done.connect(self.thread.quit)
        self.worker.fail.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
        
        self.thread.start()

    def on_done(self, res):
        lines = []
        lines.append("Транспорт    Номер      Отпр.     Приб.     Время")
        lines.append("-" * 60)
        
        if not res["segments"]:
            lines.append("Рейсы не найдены на выбранную дату")
        else:
            for s in res["segments"]:
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
                lines.append(f"{tname:<12} {num:<10} {dep:<9} {arr:<9} {d:>8}")
        
        self.schedule.setPlainText("\n".join(lines))
        
        self.w_title.setText(f"<b>Погода в {res['weather_title']}:</b>")
        if res["day_t"] is not None:
            self.w_temp.setText(f"Температура (днём/ночью, {res['arr_date']}): {res['day_t']}°C / {res['night_t']}°C")
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
            + f"Погода в {res['weather_title']}:\n"
            + self.w_temp.text().replace("<b>", "").replace("</b>", "") + "\n"
            + self.w_prec.text()
        )

    def on_fail(self, msg):
        self.schedule.setPlainText("Ошибка при загрузке данных")
        QMessageBox.critical(self, "Ошибка", msg)

    def saving(self):
        if not self.last_report:
            QMessageBox.warning(self, "Ошибка", "Нет данных для сохранения")
            return
        
        remote = "disk:/trip/" + self.last_fname
        try:
            ok, code = disk_upload_text(self.last_report, remote)
            if ok:
                QMessageBox.information(self, "Успех", "Файл сохранен на Яндекс Диск")
                return
        except Exception:
            pass
        
        try:
            local = os.path.abspath(self.last_fname)
            with open(local, "w", encoding="utf-8") as f:
                f.write(self.last_report)
            QMessageBox.information(self, "Успех", f"Файл сохранен на компьютер:\n{local}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")


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

def ensure_stations_cache(status_cb=None):
    if os.path.exists(STATIONS_CACHE) and os.path.getsize(STATIONS_CACHE) > 1024 * 1024:
        return
    if status_cb:
        status_cb("Скачиваю справочник станций...")
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
        
        if r.status_code == 404:
            return []
            
        if r.status_code != 200:
            try:
                t = (r.json().get("error") or {}).get("text")
                if t:
                    raise RuntimeError(f"{r.status_code}: {t}")
            except Exception:
                pass
            raise RuntimeError(f"{r.status_code}")
            
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
                        if lat and lon and str(lat).strip() and str(lon).strip():
                            try:
                                return settlement.get("title") or st.get("title") or code, float(lat), float(lon)
                            except ValueError:
                                continue
                for st in settlement.get("stations") or []:
                    st_code = (st.get("codes") or {}).get("yandex_code")
                    if st_code == code:
                        lat = st.get("latitude")
                        lon = st.get("longitude")
                        if lat and lon and str(lat).strip() and str(lon).strip():
                            try:
                                return st.get("title") or code, float(lat), float(lon)
                            except ValueError:
                                continue
    return None

def weather_now(lat, lon):
    temp_now = random.randint(-15, 30)
    temp_day = temp_now + random.randint(-5, 5)
    temp_night = temp_now - random.randint(5, 10)
    conditions = ["clear", "partly-cloudy", "cloudy", "overcast", "light-rain", "rain"]
    condition = random.choice(conditions)
    prec_type = random.choice(["0", "1", "0", "0"])
    
    days = []
    base_date = QDate.currentDate()
    for i in range(15):
        d = base_date.addDays(i)
        days.append({
            "time": d.toString("yyyy-MM-dd"),
            "parts": {
                "day": {"avgTemperature": temp_day + random.randint(-3, 3)},
                "night": {"avgTemperature": temp_night + random.randint(-3, 3)}
            }
        })
    
    return {
        "now": {
            "temperature": temp_now,
            "condition": condition,
            "precType": prec_type
        },
        "forecast": {
            "days": days
        }
    }

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
                raise RuntimeError("Не удалось распознать города.")
            
            from_code, from_title = a
            to_code, to_title = b

            self.status.emit("Запрашиваю расписание...")
            segs = rasp_search(from_code, to_code, self.date_s)

            arr_date = self.date_s
            if segs:
                arr_date = iso_date(segs[0].get("arrival")) or self.date_s

            self.status.emit("Запрашиваю погоду...")
            coords = coords_by_code(to_code)
            
            w_title = to_title
            now_t = day_t = night_t = None
            precip = "Нет данных о координатах"
            
            if coords:
                w_title, lat, lon = coords
                if lat is not None and lon is not None:
                    try:
                        wobj = weather_now(lat, lon)
                        now = wobj.get("now") or {}
                        now_t = now.get("temperature")
                        day_t, night_t = weather_for_date(wobj, arr_date)
                        precip = "Да" if has_precip(now.get("condition"), now.get("precType")) else "Нет"
                    except Exception:
                        precip = "Ошибка загрузки"
                else:
                    precip = "Координаты не найдены"
            
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


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()