import requests
import os
import datetime
import time
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_EMAIL = os.getenv("ALERT_EMAIL")

MAX_BUDGET = 200000  # 2L INR max
DESTINATIONS = ["LIS", "OPO"]  # Lisbon + Porto

DEPARTURE_START = datetime.date(2026, 7, 27)
DEPARTURE_END = datetime.date(2026, 7, 31)

RETURN_DAYS = 7  # trip duration
AIRLINES_ALLOWED = ["Qatar", "Emirates", "Etihad", "Lufthansa", "Air France", "KLM"]


# ---------------------------------------------------
# SEARCH FLIGHTS
# ---------------------------------------------------
def search_flights(depart_date, return_date, dest):
    print(f"Checking {dest} | Depart {depart_date}")

    url = "https://serpapi.com/search.json"

    params = {
        "engine": "google_flights",
        "departure_id": "DEL",
        "arrival_id": dest,
        "outbound_date": depart_date.strftime("%Y-%m-%d"),
        "return_date": return_date.strftime("%Y-%m-%d"),
        "currency": "INR",
        "hl": "en",
        "api_key": SERPAPI_KEY,
        "travel_class": 2,
        "deep_search": True
    }

    try:
        r = requests.get(url, params=params, timeout=60)
        data = r.json()
    except Exception as e:
        print("API error:", e)
        return []

    results = []

    if "best_flights" not in data:
        return []

    for flight in data["best_flights"]:
        price = flight.get("price", 999999)

        if price > MAX_BUDGET:
            continue

        airline_ok = False
        for f in flight.get("flights", []):
            airline = f.get("airline", "")
            if any(a.lower() in airline.lower() for a in AIRLINES_ALLOWED):
                airline_ok = True

        if not airline_ok:
            continue

        stops = len(flight.get("flights", [])) - 1
        if stops > 1:
            continue

        results.append(
            f"""
PRICE: ₹{price}
ROUTE: DEL → {dest}
DEPART: {depart_date}
RETURN: {return_date}
AIRLINE: {flight['flights'][0]['airline']}
BOOK: {flight.get('link','N/A')}
"""
        )

    return results


# ---------------------------------------------------
# SCAN ALL DATES
# ---------------------------------------------------
def scan_all():
    print("Starting GOD MODE scan...")

    deals = []

    d = DEPARTURE_START
    while d <= DEPARTURE_END:
        ret = d + datetime.timedelta(days=RETURN_DAYS)

        for dest in DESTINATIONS:
            res = search_flights(d, ret, dest)
            deals.extend(res)

        d += datetime.timedelta(days=1)
        time.sleep(2)

    return deals


# ---------------------------------------------------
# SEND EMAIL VIA SENDGRID
# ---------------------------------------------------
def send_email(results):
    if not results:
        print("No cheap flights today")
        return

    body = "\n\n".join(results)

    data = {
        "personalizations": [{"to": [{"email": ALERT_EMAIL}]}],
        "from": {"email": ALERT_EMAIL},
        "subject": "🔥 GOD MODE: Portugal Business Class Deals Found",
        "content": [{"type": "text/plain", "value": body}]
    }

    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        },
        json=data,
        timeout=30
    )

    print("SendGrid response:", r.status_code, r.text)


# ---------------------------------------------------
# RUN BOT
# ---------------------------------------------------
if __name__ == "__main__":
    results = scan_all()
    send_email(results)
