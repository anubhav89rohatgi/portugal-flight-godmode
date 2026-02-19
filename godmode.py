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

# ---------------- SCORING ----------------
def miles_value(price):
    return (price - 35000) / 140000

def deal_score(price, duration, value):
    return price/1000 + duration/15 - value*60

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

    return "Search airline site"

# ---------------- EMAIL ----------------
def send_email(results):

    subject = "🏆 TOP 5 Premium Cabin Deals"

    if not results:
        body = "No Business/Premium Economy deals found."
    else:
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
        if not price:
            continue

        print("Price:", price)

        segments = f.get("flights", [])

        if not segments:
            print("❌ No segments")
            continue

        # --- CABIN DETECTION ---
        cabin_classes = []

        for s in segments:
            cabin = s.get("travel_class") or s.get("class")
            if cabin:
                cabin_classes.append(cabin)

        print("Cabins:", cabin_classes)

        # Accept Business OR Premium Economy
        if not any(
            ("Business" in str(c) or "Premium" in str(c))
            for c in cabin_classes
        ):
            print("❌ Not premium cabin")
            continue

        # Identify dominant cabin
        if any("Business" in str(c) for c in cabin_classes):
            cabin_type = "Business Class"
        else:
            cabin_type = "Premium Economy"

        airline = segments[0].get("airline", "Unknown")

        airline_penalty = 0
        if not any(a in airline for a in AIRLINES_ALLOWED):
            airline_penalty = 40

        duration = sum(s.get("duration", 0) for s in segments)

        value = miles_value(price)
        score = deal_score(price, duration, value) + airline_penalty

        google_link = f"https://www.google.com/travel/flights?q=Flights%20from%20DEL%20to%20{dest}%20on%20{depart}"
        airline_url = airline_link(airline, "DEL", dest, depart)

        text = f"""
₹{price}
Cabin: {cabin_type}
Airline: {airline}

Route: DEL → {dest}
Depart: {depart}
Return: {ret}

Total Duration: {duration//60}h {duration%60}m

Book (Airline):
{airline_url}

View on Google Flights:
{google_link}
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
