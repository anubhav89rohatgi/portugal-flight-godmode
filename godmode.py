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

# ---------------- LEG FORMAT ----------------
def format_leg(legs):

    route = []
    total_duration = 0

    for l in legs:
        route.append(l["departure_airport"]["id"])
        total_duration += l.get("duration", 0)

    route.append(legs[-1]["arrival_airport"]["id"])

    route_str = " → ".join(route)

    # Layover calculation
    layover_info = ""
    if len(legs) > 1:
        stops = []
        for i in range(len(legs)-1):
            city = legs[i]["arrival_airport"]["id"]
            stops.append(city)
        layover_info = f"Layover: {', '.join(stops)}"

    return route_str, total_duration, layover_info

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

        # --- BUSINESS (strict) ---
        if outbound and inbound:

            out_route, out_dur, out_lay = format_leg(outbound)
            in_route, in_dur, in_lay = format_leg(inbound)

            cabins = [str(l.get("travel_class") or l.get("class")) for l in outbound+inbound]

            entry = {
                "price": price,
                "airline": outbound[0].get("airline", "Unknown"),
                "depart": depart,
                "return": ret,
                "dest": dest,
                "out_route": out_route,
                "in_route": in_route,
                "out_dur": out_dur,
                "in_dur": in_dur,
                "out_lay": out_lay,
                "in_lay": in_lay
            }

            if any("Business" in c for c in cabins):
                business.append(entry)
                continue

        # --- FALLBACK ---
        segments = f.get("flights", [])
        if not segments:
            continue

        route, dur, lay = format_leg(segments)

        entry = {
            "price": price,
            "airline": segments[0].get("airline", "Unknown"),
            "depart": depart,
            "return": ret,
            "dest": dest,
            "out_route": route,
            "in_route": "",
            "out_dur": dur,
            "in_dur": 0,
            "out_lay": lay,
            "in_lay": ""
        }

        cabins = [str(l.get("travel_class") or l.get("class")) for l in segments]

        if any("Premium" in c for c in cabins):
            premium.append(entry)
        else:
            economy.append(entry)

    return business, premium, economy

# ---------------- FORMAT ----------------
def format_flight(f, cabin):

    score, decision, confidence = booking_score(f["price"])

    return f"""
₹{f['price']}
Cabin: {cabin}
Airline: {f['airline']}

📍 Outbound:
{f['out_route']}
Duration: {f['out_dur']//60}h {f['out_dur']%60}m
{f['out_lay']}

📍 Return:
{f['in_route']}
Duration: {f['in_dur']//60}h {f['in_dur']%60}m
{f['in_lay']}

📊 Score: {score}/10 → {decision}
Confidence: {confidence}

🔗 Google Flights:
{google_link('DEL', f['dest'], f['depart'], f['return'])}

🔗 Airline:
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

    if all_business:

        all_business.sort(key=lambda x: x["price"])
        body = "🏆 TOP BUSINESS CLASS DEALS\n\n"

        for f in all_business[:5]:
            body += format_flight(f, "Business Class")

        return body

    body = "⚠️ NO BUSINESS CLASS AVAILABILITY\n\n"

    for f in sorted(all_premium, key=lambda x: x["price"])[:3]:
        body += format_flight(f, "Premium Economy")

    for f in sorted(all_economy, key=lambda x: x["price"])[:2]:
        body += format_flight(f, "Economy")

    return body

# ---------------- MAIN ----------------
if __name__ == "__main__":

    try:
        report = scan_all()
        send_email(report)
    except Exception as e:
        print("ERROR:", e)
