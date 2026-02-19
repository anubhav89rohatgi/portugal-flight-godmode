import requests
import os
import datetime
import time
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

def miles_value(price):
    return (price - 35000) / 140000

def deal_score(price, duration, value):
    return price/1000 + duration/15 - value*60

def send_email(results):

    subject = "🏆 TOP 5 Business Deals"
    body = "\n\n".join(results) if results else "No business class deals found."

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
        if not price:
            continue

        print("Price:", price)

        segments = f.get("flights", [])

        if not segments:
            print("❌ No segments")
            continue

        # --- STRICT CABIN CHECK ---
        cabin_classes = []

        for s in segments:
            cabin = s.get("travel_class") or s.get("class")
            if cabin:
                cabin_classes.append(cabin)

        print("Cabin classes detected:", cabin_classes)

        if not any("Business" in str(c) for c in cabin_classes):
            print("❌ Not business class")
            continue

        airline = segments[0].get("airline", "Unknown")

        airline_penalty = 0
        if not any(a in airline for a in AIRLINES_ALLOWED):
            airline_penalty = 40

        duration = sum(s.get("duration", 0) for s in segments)

        value = miles_value(price)
        score = deal_score(price, duration, value) + airline_penalty

        link = f"https://www.google.com/travel/flights?q=Flights%20from%20DEL%20to%20{dest}%20on%20{depart}"

        text = f"""
₹{price}
Airline: {airline}
Destination: {dest}
Depart: {depart}
Return: {ret}
Total Duration: {duration//60}h {duration%60}m
Booking: {link}
"""

        found.append({"score": score, "text": text})

    return found

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

if __name__ == "__main__":

    deals = scan_all()
    send_email(deals)
