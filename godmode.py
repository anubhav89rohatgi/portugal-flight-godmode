import requests
import os
import datetime
import time
import json
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_EMAIL = os.getenv("ALERT_EMAIL")

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")
TWILIO_TO = os.getenv("TWILIO_TO")

MAX_BUDGET = 200000
SNIPER_PRICE = 100000

DESTINATIONS = ["LIS", "OPO"]

DEPARTURE_START = datetime.date(2026, 7, 27)
DEPARTURE_END = datetime.date(2026, 7, 31)

RETURN_DAYS = 7

AIRLINES_ALLOWED = [
    "Qatar","Emirates","Etihad",
    "Lufthansa","Air France","KLM"
]

CACHE_FILE = "price_cache.json"

# ---------------- CACHE ----------------
def load_cache():
    if os.path.exists(CACHE_FILE):
        return json.load(open(CACHE_FILE))
    return {}

def save_cache(c):
    json.dump(c, open(CACHE_FILE,"w"))

# ---------------- AMEX BONUS HINT ----------------
def amex_bonus_hint(price):
    if price >= 220000:
        return "💳 Check Amex → Qatar/FlyingBlue bonus (20–40% promos common)"
    return ""

# ---------------- WHATSAPP ----------------
def send_whatsapp(msg):
    if not TWILIO_SID:
        return

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"

    requests.post(
        url,
        auth=(TWILIO_SID, TWILIO_TOKEN),
        data={
            "From": TWILIO_FROM,
            "To": TWILIO_TO,
            "Body": msg
        }
    )

# ---------------- SEARCH ----------------
def search_flights(depart_date, return_date, dest):

    cache = load_cache()

    params = {
        "engine": "google_flights",
        "departure_id": "DEL",
        "arrival_id": dest,
        "outbound_date": str(depart_date),
        "return_date": str(return_date),
        "currency": "INR",
        "api_key": SERPAPI_KEY,
        "travel_class": 2
    }

    data = requests.get(
        "https://serpapi.com/search.json",
        params=params
    ).json()

    deals = []

    for f in data.get("best_flights", []):

        price = f.get("price", 999999)
        if price > MAX_BUDGET:
            continue

        legs = f.get("flights", [])
        if not legs:
            continue

        # 1 stop max
        if len(legs) - 1 > 1:
            continue

        airline = legs[0].get("airline", "")
        if not any(a in airline for a in AIRLINES_ALLOWED):
            continue

        # duration
        total_min = sum(x.get("duration",0) for x in legs)
        duration = f"{total_min//60}h {total_min%60}m"

        # layover
        layover_city = "Direct"
        if len(legs) > 1:
            layover_city = legs[0]["arrival_airport"]["name"]

        # red-eye check
        dep_time = legs[0]["departure_airport"]["time"]
        red_eye = "🌙 Red-eye" if dep_time.startswith(("22","23","00","01","02","03")) else ""

        # price drop tracking
        key = f"{dest}_{depart_date}"
        drop = ""
        if key in cache and price < cache[key]:
            drop = f"📉 Drop ₹{cache[key]-price}"
        cache[key] = price
        save_cache(cache)

        # advice logic
        if price <= SNIPER_PRICE:
            advice = "🚨 ULTRA SNIPER FARE — BOOK NOW"
            send_whatsapp(f"🚨 SNIPER DEAL ₹{price} to {dest}! Book NOW!")
        elif price <= 160000:
            advice = "✅ Good cash fare"
        else:
            advice = "✈️ Consider miles"

        amex = amex_bonus_hint(price)

        # booking link
        link = (
            f"https://www.google.com/travel/flights?"
            f"#flt=DEL.{dest}.{depart_date}*"
            f"{dest}.DEL.{return_date};c:INR;e:1;sc:b"
        )

        deals.append(f"""
💺 BUSINESS CLASS

₹{price} {drop}
{advice}

Airline: {airline}
Total Time: {duration}
Layover: {layover_city}
Depart: {dep_time} {red_eye}

{amex}

BOOK HERE:
{link}
""")

    return deals

# ---------------- EMAIL ----------------
def send_email(results):

    if not results:
        print("No deals found")
        return

    body = "\n\n".join(results)

    requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "personalizations":[{"to":[{"email":ALERT_EMAIL}]}],
            "from":{"email":ALERT_EMAIL},
            "subject":"✈️ ULTIMATE Portugal Flight Alerts",
            "content":[{"type":"text/plain","value":body}]
        }
    )

# ---------------- SCAN LOOP ----------------
def scan_all():
    all_deals = []
    d = DEPARTURE_START

    while d <= DEPARTURE_END:
        r = d + datetime.timedelta(days=RETURN_DAYS)

        for dest in DESTINATIONS:
            all_deals += search_flights(d, r, dest)

        d += datetime.timedelta(days=1)

    return all_deals

# ---------------- RUN EVERY 8 HOURS ----------------
if __name__ == "__main__":

    while True:
        print("Running scan...")
        deals = scan_all()
        send_email(deals)

        print("Sleeping 8 hours...")
        time.sleep(28800)
