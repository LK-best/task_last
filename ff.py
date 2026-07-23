import sys
import requests

SECRET = "45ba08b6-f0f5-48a3-aadb-85de5791adf0"
API_URL = "https://api.rasp.yandex.net/v3/search/"


def start():
    data = sys.stdin.read().split()
    fr, to, date = data[0], data[1], data[2]

    trains = set()
    page = 1

    while True:
        params = {
            "apikey": SECRET,
            "from": fr,
            "to": to,
            "date": date,
            "transport_types": "train",
            "page": page,
        }

        res = requests.get(API_URL, params=params, timeout=20)
        res.raise_for_status()
        out = res.json()

        for segment in out.get("segments", []):
            title = segment.get("thread", {}).get("title")
            if title:
                trains.add(title)

        pagination = out.get("pagination", {})
        page_count = pagination.get("page_count", 1)
        if page >= page_count:
            break
        page += 1

    for t in sorted(trains):
        print(t)


if __name__ == "__main__":
    start()