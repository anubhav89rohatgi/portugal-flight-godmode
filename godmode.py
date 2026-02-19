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

# ---------------- FORMAT LEG ----------------
def format_leg(legs):

    route = []
    duration = 0

    for l in legs:
        route.append(l["departure_airport"]["id"])
        duration += l.get("duration", 0)

    route.append(legs[-1]["arrival_airport"]["id"])

    layovers = []
    if len(legs) > 1:
        for i in range(len(legs)-1):
            layovers.append(legs[i]["arrival_airport"]["id"])

    return {
        "route": " → ".join(route),
        "duration": duration,
        "layover": ", ".join(layovers) if layovers else "Direct"
    }

# ---------------- FETCH ONE-WAY ----------------
def fetch_oneway(origin, dest, date):

    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": dest,
        "outbound_date": str(date),
        "currency": "INR",
        "api_key": SERPAPI_KEY,
        "travel_class": 2,
        "deep_search": True
    }

    r = requests.get("https://serpapi.com/search.json", params=params)
    data = r.json()

    return data.get("best_flights", [])

# ---------------- SEARCH ----------------
def search_dual(depart, ret, dest):

    outbound_list = fetch_oneway("DEL", dest, depart)
    inbound_list = fetch_oneway(dest, "DEL", ret)

    results = []

    for out in outbound_list[:5]:
        for inc in inbound_list[:5]:

            out_legs = out.get("flights", [])
            in_legs = inc.get("flights", [])

            if not out_legs or not in_legs:
                continue

            # --- CABIN FILTER ---
            cabins = [
                str(l.get("travel_class") or l.get("class"))
                for l in (out_legs + in_legs)
            ]

            if not any("Business" in c for c in cabins):
                continue

            price = (out.get("price", 0) + inc.get("price", 0))

            airline = out_legs[0].get("airline", "Unknown")

            out_info = format_leg(out_legs)
            in_info = format_leg(in_legs)

            entry = {
                "price": price,
                "airline": airline,
                "depart": depart,
                "return": ret,
                "dest": dest,
                "out": out_info,
                "in": in_info
            }

            results.append(entry)

    return results

# ---------------- FORMAT ----------------
def format_flight(f):

    score, decision, confidence = booking_score(f["price"])

    return f"""
₹{f['price']} (Combined)
Airline: {f['airline']}

📍 Outbound:
{f['out']['route']}
Duration: {f['out']['duration']//60}h {f['out']['duration']%60}m
Layover: {f['out']['layover']}

📍 Return:
{f['in']['route']}
Duration: {f['in']['duration']//60}h {f['in']['duration']%60}m
Layover: {f['in']['layover']}

📊 Score: {score}/10 → {decision}
Confidence: {confidence}

🔗 Google Flights:
{google_link('DEL', f['dest'], f['depart'], f['return'])}

🔗 Airline:
{airline_link(f['airline'], 'DEL', f['dest'])}
"""

# ---------------- SCAN ----------------
def scan_all():

    all_results = []

    d = DEPARTURE_START

    while d <= DEPARTURE_END:

        r = d + datetime.timedelta(days=RETURN_DAYS)

        for dest in DESTINATIONS:
            print(f"Checking {dest} | {d}")
            all_results += search_dual(d, r, dest)

        d += datetime.timedelta(days=1)

    all_results.sort(key=lambda x: x["price"])

    top = all_results[:5]

    if not top:
        return "⚠️ No Business Class combinations found."

    body = "🏆 TOP BUSINESS CLASS ROUND-TRIP DEALS\n\n"

    for f in top:
        body += format_flight(f)

    return body

# ---------------- MAIN ----------------
if __name__ == "__main__":

    try:
        report = scan_all()
        send_email(report)
    except Exception as e:
        print("ERROR:", e)
