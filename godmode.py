import requests
import os
import datetime
import time
import sys
from dotenv import load_dotenv

print("=== BOT FILE STARTED ===")

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_EMAIL = os.getenv("ALERT_EMAIL")

MAX_BUDGET = 600000
SNIPER_PRICE = 100000

DESTINATIONS = ["LIS", "OPO"]

BASE_DEPARTURE = datetime.date(2026, 7, 31)
DEPARTURE_START = BASE_DEPARTURE - datetime.timedelta(days=2)
DEPARTURE_END = BASE_DEPARTURE + datetime.timedelta(days=2)
RETURN_DAYS = 7

AIRLINES_ALLOWED = [
    "Qatar", "Emirates", "Etihad",
    "Lufthansa", "Air France", "KLM"
]

# ---------------- SCORING ----------------
def miles_value_check(price):
    miles = 140000
    taxes = 35000
    return (price - taxes) / miles

def deal_score(price, total_minutes, value):
    return price/1000 + total_minutes/15 - value*60

def airline_link(origin, dest, date):
    return f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}%20on%20{date}"

# ---------------- EMAIL ----------------
def send_email(results):

    subject = "🏆 TOP 5 Business Deals"
    body = "\n\n".join(results) if results else "No deals found."

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

    r = requests.get("https://serpapi.com/search.json", params=params)
    data = r.json()

    flights = data.get("best_flights", [])
    print("Flights returned:", len(flights))

    found = []

    for f in flights:

        price = f.get("price")
        print("Price:", price)

        if not price:
            continue

        if price > MAX_BUDGET:
            continue

        # ---- FLEXIBLE STRUCTURE HANDLING ----
        segments = []

        if "flights" in f:
            segments = f["flights"]

        elif "outbound_flights" in f:
            segments += f.get("outbound_flights", [])
            segments += f.get("return_flights", [])

        if not segments:
            print("❌ No segment data")
            continue

        airline = segments[0].get("airline", "Unknown")

        airline_penalty = 0
        if not any(a in airline for a in AIRLINES_ALLOWED):
            airline_penalty = 40

        total_minutes = sum(s.get("duration", 0) for s in segments)

        value = miles_value_check(price)
        score = deal_score(price, total_minutes, value) + airline_penalty

        link = airline_link("DEL", dest, depart)

        text = f"""
₹{price}
Airline: {airline}
Destination: {dest}
Depart: {depart}
Return: {ret}
Total Duration: {total_minutes//60}h {total_minutes%60}m
Booking: {link}
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

    try:
        deals = scan_all()
        send_email(deals)
    except Exception as e:
        print("ERROR:", e)
