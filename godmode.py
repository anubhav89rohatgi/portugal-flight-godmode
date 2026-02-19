import requests
import os
import datetime
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

# ---------------- BOOK / WAIT ENGINE ----------------
def booking_score(price, duration, airline, value):

    # Base score from price
    if price < 120000:
        score = 9
    elif price < 150000:
        score = 7.5
    elif price < 200000:
        score = 6
    else:
        score = 4

    # Duration adjustment
    if duration < 900:   # <15h
        score += 0.5
    elif duration > 1200:
        score -= 0.5

    # Airline preference
    if any(a in airline for a in AIRLINES_ALLOWED):
        score += 0.5

    # Miles value bonus
    if value > 2:
        score += 0.5

    # Clamp
    score = max(1, min(10, round(score, 1)))

    # Label
    if score >= 8:
        decision = "🔥 BOOK NOW"
        confidence = "High"
    elif score >= 6:
        decision = "👍 Good Deal"
        confidence = "Medium"
    else:
        decision = "⏳ WAIT"
        confidence = "Low"

    return score, decision, confidence

# ---------------- LINKS ----------------
def airline_homepage(airline):
    if "Qatar" in airline:
        return "https://www.qatarairways.com"
    if "Emirates" in airline:
        return "https://www.emirates.com"
    if "Etihad" in airline:
        return "https://www.etihad.com"
    if "Lufthansa" in airline:
        return "https://www.lufthansa.com"
    if "Air France" in airline:
        return "https://www.airfrance.com"
    if "KLM" in airline:
        return "https://www.klm.com"
    return "Search airline"

def google_link(origin, dest, depart, ret):
    return f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}%20on%20{depart}%20return%20{ret}"

# ---------------- EMAIL ----------------
def send_email(results):

    subject = "🏆 TOP 5 Business Class Deals"

    if not results:
        body = "No Business Class deals found."
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

        segments = f.get("flights", [])
        if not segments:
            continue

        # --- BUSINESS CLASS FILTER ---
        cabins = [s.get("travel_class") or s.get("class") for s in segments]

        if not any("Business" in str(c) for c in cabins):
            continue

        airline = segments[0].get("airline", "Unknown")
        duration = sum(s.get("duration", 0) for s in segments)

        value = miles_value(price)
        score = deal_score(price, duration, value)

        book_score, decision, confidence = booking_score(
            price, duration, airline, value
        )

        g_link = google_link("DEL", dest, depart, ret)
        a_link = airline_homepage(airline)

        text = f"""
₹{price}
Cabin: Business Class
Airline: {airline}

Route: DEL → {dest}
Depart: {depart}
Return: {ret}

Total Duration: {duration//60}h {duration%60}m

📊 Book Score: {book_score}/10
Decision: {decision}
Confidence: {confidence}

🔗 Google Flights:
{g_link}

🔗 Airline:
{a_link}
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
            ranked += search_flights(d, r, dest)

        d += datetime.timedelta(days=1)

    ranked.sort(key=lambda x: x["score"])
    results = [x["text"] for x in ranked[:5]]

    print(f"Deals found: {len(results)}")

    return results

# ---------------- MAIN ----------------
if __name__ == "__main__":

    deals = scan_all()
    send_email(deals)
