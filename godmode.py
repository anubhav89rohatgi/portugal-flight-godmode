import requests
import os
import datetime
import time
import json
import sys
from dotenv import load_dotenv

print("=== BOT FILE STARTED ===")

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_EMAIL = os.getenv("ALERT_EMAIL")

TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")
TWILIO_TO = os.getenv("TWILIO_TO")

MAX_BUDGET = 300000
SNIPER_PRICE = 100000

DESTINATIONS = ["LIS", "OPO"]

# === FIXED TRAVEL WINDOW ===
BASE_DEPARTURE = datetime.date(2026, 7, 31)
DEPARTURE_START = BASE_DEPARTURE - datetime.timedelta(days=2)
DEPARTURE_END = BASE_DEPARTURE + datetime.timedelta(days=2)
RETURN_DAYS = 7

AIRLINES_ALLOWED = [
    "Qatar", "Emirates", "Etihad",
    "Lufthansa", "Air France", "KLM"
]

# ---------------- MILES ENGINE ----------------
def estimate_miles(dest):
    return 140000

def miles_value_check(price, dest):
    miles = estimate_miles(dest)
    taxes = 35000
    value = (price - taxes) / miles

    if value > 2:
        label = f"🔥 GREAT VALUE (~₹{round(value,2)}/mile)"
    elif value > 1.4:
        label = f"👍 OK VALUE (~₹{round(value,2)}/mile)"
    else:
        label = "❌ Poor miles value"

    return label, value

# ---------------- DEAL SCORE ----------------
def deal_score(price, total_minutes, value):
    return price/1000 + total_minutes/15 - value*60

# ---------------- AIRLINE LINKS ----------------
def airline_link(airline, origin, dest, date):
    date = str(date)

    if "Qatar" in airline:
        return f"https://www.qatarairways.com/en-in/book-a-flight.html?from={origin}&to={dest}&date={date}"
    if "Emirates" in airline:
        return f"https://www.emirates.com/in/english/book/?origin={origin}&destination={dest}&departureDate={date}"
    if "Etihad" in airline:
        return f"https://www.etihad.com/en-in/book?origin={origin}&destination={dest}&departureDate={date}"
    if "Lufthansa" in airline:
        return f"https://www.lufthansa.com/in/en/booking?origin={origin}&destination={dest}&outboundDate={date}"
    if "Air France" in airline:
        return f"https://wwws.airfrance.co.in/search/flights?origin={origin}&destination={dest}&date={date}"
    if "KLM" in airline:
        return f"https://www.klm.co.in/search?origin={origin}&destination={dest}&date={date}"

    return "Search airline website"

# ---------------- EMAIL ----------------
def send_email(results):

    if not results:
        subject = "Flight Bot Update (No Deals)"
        body = "No good deals found.\nBot running fine ✅"
    else:
        subject = "🏆 TOP 5 Business Class Deals"
        body = "\n\n".join(results)

    requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "personalizations":[{"to":[{"email": ALERT_EMAIL}]}],
            "from":{"email": ALERT_EMAIL},
            "subject": subject,
            "content":[{"type":"text/plain","value": body}]
        }
    )

    print("Email sent")

# ---------------- ERROR EMAIL ----------------
def send_error_email(err):

    body = f"""
⚠️ BOT ERROR

{err}

Time: {datetime.datetime.now()}
"""

    requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "personalizations":[{"to":[{"email": ALERT_EMAIL}]}],
            "from":{"email": ALERT_EMAIL},
            "subject":"⚠️ BOT ERROR ALERT",
            "content":[{"type":"text/plain","value": body}]
        }
    )

# ---------------- SEARCH ----------------
def search_flights(depart, ret, dest):

    print(f"\n🔎 Searching {dest} | Depart {depart}")

    params = {
        "engine": "google_flights",
        "departure_id": "DEL",
        "arrival_id": dest,
        "outbound_date": str(depart),
        "return_date": str(ret),
        "currency": "INR",
        "api_key": SERPAPI_KEY,
        "travel_class": 2,
        "deep_search": True
    }

    try:
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
        data = r.json()
        print("Flights returned:", len(data.get("best_flights", [])))
    except Exception as e:
        print("API ERROR:", e)
        return []

    found = []

    for f in data.get("best_flights", []):

        price = f.get("price", 999999)

        if price > MAX_BUDGET:
            continue

        outbound = f.get("outbound_flights") or []
        inbound = f.get("return_flights") or []

        if not outbound or not inbound:
            continue

        airline = outbound[0].get("airline", "Unknown")

        # Soft airline penalty instead of rejection
        airline_penalty = 0
        if not any(a in airline for a in AIRLINES_ALLOWED):
            airline_penalty = 40

        def mins(x):
            return sum(l.get("duration", 0) for l in x)

        total = mins(outbound) + mins(inbound)

        miles_label, val = miles_value_check(price, dest)

        if price <= SNIPER_PRICE:
            print("🚨 SNIPER TRIGGERED")
        
        link = airline_link(airline, "DEL", dest, depart)

        score = deal_score(price, total, val) + airline_penalty

        text = f"""
₹{price}
Airline: {airline}
Destination: {dest}
Depart: {depart}
Return: {ret}

Total Duration: {total//60}h {total%60}m

Miles Value:
{miles_label}

Book:
{link}
"""

        found.append({"score": score, "text": text})

    return found

# ---------------- SCAN ----------------
def scan_all():

    ranked = []
    d = DEPARTURE_START

    print("=== SCAN START ===")

    while d <= DEPARTURE_END:

        r = d + datetime.timedelta(days=RETURN_DAYS)

        for dest in DESTINATIONS:
            print(f"Checking {dest} | {d}")
            ranked += search_flights(d, r, dest)

        d += datetime.timedelta(days=1)

    ranked.sort(key=lambda x: x["score"])

    results = [x["text"] for x in ranked[:5]]

    print(f"Deals found: {len(results)}")

    return results

# ---------------- MAIN ----------------
if __name__ == "__main__":

    if "runonce" in sys.argv:

        print("=== AD-HOC RUN ===")

        try:
            deals = scan_all()
            send_email(deals)
        except Exception as e:
            print("ERROR:", e)
            send_error_email(str(e))

    else:

        while True:

            try:
                deals = scan_all()
                send_email(deals)
            except Exception as e:
                send_error_email(str(e))

            print("Sleeping 8h...")
            time.sleep(28800)
