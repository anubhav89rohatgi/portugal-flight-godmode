import requests
import os
import datetime
import time
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_EMAIL = os.getenv("ALERT_EMAIL")

MAX_BUDGET = 200000
SNIPER_PRICE = 140000

DESTINATIONS = ["LIS", "OPO"]

DEPARTURE_START = datetime.date(2026, 7, 27)
DEPARTURE_END = datetime.date(2026, 7, 31)

RETURN_DAYS = 7

AIRLINES_ALLOWED = [
    "Qatar",
    "Emirates",
    "Etihad",
    "Lufthansa",
    "Air France",
    "KLM"
]

# ---------------------------------------------------
# MILES + BONUS INTELLIGENCE
# ---------------------------------------------------
def miles_advice(price):

    if price <= SNIPER_PRICE:
        return "🚨 MISTAKE FARE — BOOK NOW"

    elif price <= 160000:
        return "✅ PAY CASH (great deal)"

    elif price >= 220000:
        return "✈️ USE AMEX MILES\n💳 Check AMEX → Qatar / FlyingBlue transfer bonuses"

    else:
        return "🤔 CASH vs MILES — compare"


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
    except:
        return []

    deals = []

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

        advice = miles_advice(price)

        deals.append(f"""
PRICE: ₹{price}
ADVICE: {advice}
ROUTE: DEL → {dest}
DEPART: {depart_date}
RETURN: {return_date}
AIRLINE: {flight['flights'][0]['airline']}
BOOK: {flight.get('link','N/A')}
""")

    return deals


# ---------------------------------------------------
# SCAN DATES
# ---------------------------------------------------
def scan_all():

    print("Starting GOD MODE scan...")

    all_deals = []

    d = DEPARTURE_START

    while d <= DEPARTURE_END:

        ret = d + datetime.timedelta(days=RETURN_DAYS)

        for dest in DESTINATIONS:
            deals = search_flights(d, ret, dest)
            all_deals.extend(deals)

        d += datetime.timedelta(days=1)
        time.sleep(2)

    return all_deals


# ---------------------------------------------------
# SEND EMAIL
# ---------------------------------------------------
def send_email(results):

    if not results:
        print("No good deals today")
        return

    body = "\n\n".join(results)

    data = {
        "personalizations": [{"to": [{"email": ALERT_EMAIL}]}],
        "from": {"email": ALERT_EMAIL},
        "subject": "🔥 GOD MODE: Portugal Flight Sniper Alert",
        "content": [{"type": "text/plain", "value": body}]
    }

    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        },
        json=data
    )

    print("SendGrid status:", r.status_code)


# ---------------------------------------------------
# RUN EVERY 8 HOURS
# ---------------------------------------------------
if __name__ == "__main__":

    while True:

        results = scan_all()
        send_email(results)

        print("Sleeping 8 hours...")
        time.sleep(14400)
