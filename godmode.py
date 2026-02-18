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
    return price/1000 + total_minutes/10 - value_per_mile*50

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

    return "Search airline website"

# ---------------- WHATSAPP ----------------
def send_whatsapp(msg):
    if not TWILIO_SID:
        return

    requests.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
        auth=(TWILIO_SID,TWILIO_TOKEN),
        data={"From":TWILIO_FROM,"To":TWILIO_TO,"Body":msg}
    )

# ---------------- EMAIL ----------------
def send_email(results):

    if not results:
        print("No deals to send")
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
            "subject":"🏆 TOP 5 Flight Deals",
            "content":[{"type":"text/plain","value":body}]
        }
    )

def send_error_email(error_msg):

    body=f"""
⚠️ Flight Bot Error

Error:
{error_msg}

Time:
{datetime.datetime.now()}
"""

    requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization":f"Bearer {SENDGRID_API_KEY}",
            "Content-Type":"application/json"
        },
        json={
            "personalizations":[{"to":[{"email":ALERT_EMAIL}]}],
            "from":{"email":ALERT_EMAIL},
            "subject":"⚠️ BOT ERROR ALERT",
            "content":[{"type":"text/plain","value":body}]
        }
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

    r=requests.get("https://serpapi.com/search.json",params=params,timeout=30)
    data=r.json()

    found=[]

    for f in data.get("best_flights",[]):

        price=f.get("price",999999)
        if price>MAX_BUDGET:
            continue

        out=f.get("outbound_flights",[])
        inc=f.get("return_flights",[])
        if not out or not inc:
            continue

        if len(out)-1>1 or len(inc)-1>1:
            continue

        airline=out[0]["airline"]
        if not any(a in airline for a in AIRLINES_ALLOWED):
            continue

        def leg_minutes(legs):
            return sum(x["duration"] for x in legs)

        out_total=leg_minutes(out)
        in_total=leg_minutes(inc)
        roundtrip_total=out_total+in_total

        def fmt(m):
            return f"{m//60}h {m%60}m"

        def build_path(legs):
            return "\n".join(
                f"{l['departure_airport']['id']} {l['departure_airport']['time']} → "
                f"{l['arrival_airport']['id']} {l['arrival_airport']['time']}"
                for l in legs
            )

        out_path=build_path(out)
        in_path=build_path(inc)

        out_lay=out[0]["arrival_airport"]["id"] if len(out)>1 else "Direct"
        in_lay=inc[0]["arrival_airport"]["id"] if len(inc)>1 else "Direct"

        key=f"{dest}_{depart_date}"
        drop=""
        if key in cache and price<cache[key]:
            drop=f"📉 Drop ₹{cache[key]-price}"
        cache[key]=price
        save_cache(cache)

        miles_label,val=miles_value_check(price,dest)

        if price<=SNIPER_PRICE:
            advice="🚨 ULTRA SNIPER — BOOK NOW"
            send_whatsapp(f"🚨 SNIPER ₹{price} to {dest}!")
        elif price<=160000:
            advice="✅ Good cash fare"
        else:
            advice="✈️ Consider miles"

        link=airline_link(airline,"DEL",dest,depart_date)
        score=deal_score(price,roundtrip_total,val)

        text=f"""
💺 BUSINESS CLASS

₹{price} {drop}
{advice}

Airline: {airline}
Total: {fmt(roundtrip_total)}

OUTBOUND ({fmt(out_total)} | {out_lay})
{out_path}

RETURN ({fmt(in_total)} | {in_lay})
{in_path}

MILES:
{miles_label}

BOOK:
{link}
"""

        found.append({"score":score,"text":text})

    return found

# ---------------- SCAN ----------------
def scan_all():
    ranked=[]
    d=DEPARTURE_START

    while d<=DEPARTURE_END:
        r=d+datetime.timedelta(days=RETURN_DAYS)
        for dest in DESTINATIONS:
            ranked+=search_flights(d,r,dest)
        d+=datetime.timedelta(days=1)

    ranked.sort(key=lambda x:x["score"])
    return [x["text"] for x in ranked[:5]]

# ---------------- MAIN LOOP ----------------
if __name__=="__main__":

    while True:

        try:
            print("=== SCAN START ===")

            try:
                deals=scan_all()
            except Exception as e:
                print("Retrying scan...")
                time.sleep(10)
                deals=scan_all()

            print(f"Deals found: {len(deals)}")

            send_email(deals)
            print("Email sent")

        except Exception as e:
            print("ERROR:",e)
            send_error_email(str(e))

        print("Sleeping 8h...")
        time.sleep(28800)
