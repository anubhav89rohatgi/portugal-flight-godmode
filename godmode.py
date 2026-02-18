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

DESTINATIONS = ["LIS","OPO"]

DEPARTURE_START = datetime.date(2026,7,27)
DEPARTURE_END = datetime.date(2026,7,31)

RETURN_DAYS = 7

AIRLINES_ALLOWED = [
    "Qatar","Emirates","Etihad",
    "Lufthansa","Air France","KLM"
]

CACHE_FILE="price_cache.json"

# ---------------- CACHE ----------------
def load_cache():
    if os.path.exists(CACHE_FILE):
        return json.load(open(CACHE_FILE))
    return {}

def save_cache(c):
    json.dump(c, open(CACHE_FILE,"w"))

# ---------------- AWARD ENGINE ----------------
def estimate_miles(dest):
    return 140000

def miles_value_check(price,dest):
    miles=estimate_miles(dest)
    taxes=35000
    value=(price-taxes)/miles

    if value>2:
        label=f"🔥 GREAT VALUE (~₹{round(value,2)}/mile)"
    elif value>1.4:
        label=f"👍 OK VALUE (~₹{round(value,2)}/mile)"
    else:
        label="❌ Poor miles value"

    return label,value

# ---------------- DEAL SCORING ----------------
def deal_score(price,total_minutes,value_per_mile):
    return (
        price/1000 +
        total_minutes/10 -
        value_per_mile*50
    )

# ---------------- AIRLINE LINKS ----------------
def airline_link(airline,origin,dest,date):
    date=str(date)

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

    return "Search on airline website"

# ---------------- WHATSAPP ----------------
def send_whatsapp(msg):
    if not TWILIO_SID:
        return

    url=f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"

    requests.post(
        url,
        auth=(TWILIO_SID,TWILIO_TOKEN),
        data={"From":TWILIO_FROM,"To":TWILIO_TO,"Body":msg}
    )

# ---------------- SEARCH ----------------
def search_flights(depart_date,return_date,dest):

    cache=load_cache()

    params={
        "engine":"google_flights",
        "departure_id":"DEL",
        "arrival_id":dest,
        "outbound_date":str(depart_date),
        "return_date":str(return_date),
        "currency":"INR",
        "api_key":SERPAPI_KEY,
        "travel_class":2
    }

    data=requests.get(
        "https://serpapi.com/search.json",
        params=params
    ).json()

    found=[]

    for f in data.get("best_flights",[]):

        price=f.get("price",999999)
        if price>MAX_BUDGET:
            continue

        outbound=f.get("outbound_flights",[])
        inbound=f.get("return_flights",[])

        if not outbound or not inbound:
            continue

        airline=outbound[0].get("airline","")
        if not any(a in airline for a in AIRLINES_ALLOWED):
            continue

        if len(outbound)-1>1 or len(inbound)-1>1:
            continue

        # ----- durations -----
        def leg_minutes(legs):
            return sum(x["duration"] for x in legs)

        out_total=leg_minutes(outbound)
        in_total=leg_minutes(inbound)
        roundtrip_total=out_total+in_total

        def fmt(m):
            return f"{m//60}h {m%60}m"

        # ----- paths -----
        def build_path(legs):
            lines=[]
            for leg in legs:
                dep=leg["departure_airport"]["id"]
                arr=leg["arrival_airport"]["id"]
                dt=leg["departure_airport"]["time"]
                at=leg["arrival_airport"]["time"]
                lines.append(f"{dep} {dt} → {arr} {at}")
            return "\n".join(lines)

        out_path=build_path(outbound)
        in_path=build_path(inbound)

        # ----- layovers -----
        out_lay=outbound[0]["arrival_airport"]["id"] if len(outbound)>1 else "Direct"
        in_lay=inbound[0]["arrival_airport"]["id"] if len(inbound)>1 else "Direct"

        # ----- price drop -----
        key=f"{dest}_{depart_date}"
        drop=""
        if key in cache and price<cache[key]:
            drop=f"📉 Drop ₹{cache[key]-price}"
        cache[key]=price
        save_cache(cache)

        # ----- miles value -----
        miles_label,value_per_mile=miles_value_check(price,dest)

        # ----- advice -----
        if price<=SNIPER_PRICE:
            advice="🚨 ULTRA SNIPER — BOOK NOW"
            send_whatsapp(f"🚨 SNIPER ₹{price} to {dest}! BOOK NOW!")
        elif price<=160000:
            advice="✅ Good cash fare"
        else:
            advice="✈️ Consider miles"

        link=airline_link(airline,"DEL",dest,depart_date)

        score=deal_score(price,roundtrip_total,value_per_mile)

        text=f"""
💺 BUSINESS CLASS ROUNDTRIP

₹{price} {drop}
{advice}

Airline: {airline}
TOTAL TIME: {fmt(roundtrip_total)}

────────────
OUTBOUND
Duration: {fmt(out_total)}
Layover: {out_lay}
{out_path}

────────────
RETURN
Duration: {fmt(in_total)}
Layover: {in_lay}
{in_path}

MILES VALUE:
{miles_label}

🎯 BOOK HERE:
{link}
"""

        found.append({
            "score":score,
            "text":text
        })

    return found

# ---------------- SCAN & RANK ----------------
def scan_all():

    ranked=[]

    d=DEPARTURE_START
    while d<=DEPARTURE_END:
        r=d+datetime.timedelta(days=RETURN_DAYS)

        for dest in DESTINATIONS:
            ranked+=search_flights(d,r,dest)

        d+=datetime.timedelta(days=1)

    ranked.sort(key=lambda x:x["score"])

    top5=ranked[:5]

    return [x["text"] for x in top5]

# ---------------- EMAIL ----------------
def send_email(results):

    if not results:
        print("No deals")
        return

    body="\n\n".join(results)

    requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization":f"Bearer {SENDGRID_API_KEY}",
            "Content-Type":"application/json"
        },
        json={
            "personalizations":[{"to":[{"email":ALERT_EMAIL}]}],
            "from":{"email":ALERT_EMAIL},
            "subject":"🏆 TOP 5 Portugal Business Class Deals",
            "content":[{"type":"text/plain","value":body}]
        }
    )

# ---------------- LOOP ----------------
if __name__=="__main__":
    while True:
        print("Scanning...")
        deals=scan_all()
        send_email(deals)
        print("Sleeping 8h")
        time.sleep(28800)
