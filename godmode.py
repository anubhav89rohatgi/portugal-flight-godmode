import requests
import os
import datetime
from dotenv import load_dotenv

print("=== BOT FILE STARTED ===")

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_EMAIL = os.getenv("ALERT_EMAIL")

DESTINATIONS = ["LIS", "OPO"]

BASE_DEPARTURE = datetime.date(2026, 7, 31)
DEPARTURE_START = BASE_DEPARTURE - datetime.timedelta(days=2)
DEPARTURE_END = BASE_DEPARTURE + datetime.timedelta(days=2)
RETURN_DAYS = 7

# ---------------- BOOK SCORE ----------------
def booking_score(price):
    if price < 120000:
        return 9, "🔥 BOOK NOW", "High"
    elif price < 150000:
        return 7.5, "👍 Good Deal", "Medium"
    elif price < 200000:
        return 6, "🤔 Consider", "Medium"
    else:
        return 4, "⏳ Wait", "Low"

# ---------------- LINKS ----------------
def google_link(origin, dest, depart, ret):
    return f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}%20on%20{depart}%20return%20{ret}"

def airline_link(airline, origin, dest):
    return f"https://www.google.com/search?q={airline}+{origin}+to+{dest}+flights"

# ---------------- EMAIL ----------------
def send_email(body):

    requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "personalizations":[{"to":[{"email": ALERT_EMAIL}]}],
            "from":{"email": ALERT_EMAIL},
            "subject": "✈️ Flight Intelligence Report",
            "content":[{"type":"text/plain","value": body}]
        }
    )

    print("Email sent")

# ---------------- SEARCH ----------------
def search_flights(depart, ret, dest):

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

    business, premium, economy = [], [], []

    for f in flights:

        price = f.get("price")
        if not price:
            continue

        outbound = f.get("outbound_flights", [])
        inbound = f.get("return_flights", [])

        # ❗ CRITICAL FIX: ensure round-trip exists
        if not outbound or not inbound:
            continue

        def extract(legs):
            duration = sum(l.get("duration", 0) for l in legs)
            airline = legs[0].get("airline", "Unknown")
            cabins = [str(l.get("travel_class") or l.get("class")) for l in legs]
            return duration, airline, cabins

        out_dur, airline, cabins_out = extract(outbound)
        in_dur, _, cabins_in = extract(inbound)

        total_duration = out_dur + in_dur
        cabins = cabins_out + cabins_in

        entry = {
            "price": price,
            "duration": total_duration,
            "airline": airline,
            "depart": depart,
            "return": ret,
            "dest": dest
        }

        if any("Business" in c for c in cabins):
            business.append(entry)
        elif any("Premium" in c for c in cabins):
            premium.append(entry)
        else:
            economy.append(entry)

    return business, premium, economy

# ---------------- FORMAT ----------------
def format_flight(f, cabin):

    score, decision, confidence = booking_score(f["price"])

    return f"""
₹{f['price']} (ROUND TRIP)
Cabin: {cabin}
Airline: {f['airline']}

Route: DEL ↔ {f['dest']}
Depart: {f['depart']}
Return: {f['return']}

Total Duration: {f['duration']//60}h {f['duration']%60}m

📊 Score: {score}/10 → {decision}
Confidence: {confidence}

🔗 Google Flights:
{google_link('DEL', f['dest'], f['depart'], f['return'])}

🔗 Airline Search:
{airline_link(f['airline'], 'DEL', f['dest'])}
"""

# ---------------- SCAN ----------------
def scan_all():

    all_business, all_premium, all_economy = [], [], []

    d = DEPARTURE_START

    while d <= DEPARTURE_END:

        r = d + datetime.timedelta(days=RETURN_DAYS)

        for dest in DESTINATIONS:
            b, p, e = search_flights(d, r, dest)
            all_business += b
            all_premium += p
            all_economy += e

        d += datetime.timedelta(days=1)

    # -------- BUSINESS --------
    if all_business:

        all_business.sort(key=lambda x: x["price"])
        top = all_business[:5]

        body = "🏆 TOP BUSINESS CLASS ROUND-TRIP DEALS\n\n"

        for f in top:
            body += format_flight(f, "Business Class")

        return body

    # -------- FALLBACK --------
    body = "⚠️ NO BUSINESS CLASS AVAILABILITY\n\n"

    if all_premium:
        body += "Closest Premium Economy Options:\n"
        for f in sorted(all_premium, key=lambda x: x["price"])[:3]:
            body += format_flight(f, "Premium Economy")

    if all_economy:
        body += "\nEconomy Reference:\n"
        for f in sorted(all_economy, key=lambda x: x["price"])[:2]:
            body += format_flight(f, "Economy")

    body += "\n📊 Insight:\nBusiness fares not available or priced high."

    return body

# ---------------- MAIN ----------------
if __name__ == "__main__":

    try:
        report = scan_all()
        send_email(report)
    except Exception as e:
        print("ERROR:", e)
