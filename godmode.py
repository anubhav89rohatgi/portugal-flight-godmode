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
SNIPER_PRICE = 150000

DESTINATIONS = ["LIS","OPO"]

# ---- Use nearer dates so data exists ----
DEPARTURE_START = datetime.date.today() + datetime.timedelta(days=30)
DEPARTURE_END   = datetime.date.today() + datetime.timedelta(days=35)

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

# ---------------- DEAL SCORE ----------------
def deal_score(price,total_minutes,value):
    return price/1000 + total_minutes/10 - value*50

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
        subject="Flight Bot Update (No Deals)"
        body="No good deals found.\nBot running fine ✅"
    else:
        subject="🏆 TOP 5 Flight Deals"
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
            "subject":subject,
            "content":[{"type":"text/plain","value":body}]
        }
    )

    print("Email sent")

# ---------------- ERROR EMAIL ----------------
def send_error_email(err):

    body=f"""
⚠️ BOT ERROR

{err}

Time: {datetime.datetime.now()}
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
def search_flights(depart,ret,dest):

    cache=load_cache()

    params={
        "engine":"google_flights",
        "departure_id":"DEL",
        "arrival_id":dest,
        "outbound_date":str(depart),
        "return_date":str(ret),
        "currency":"INR",
        "api_key":SERPAPI_KEY,
        "travel_class":2
    }

    r=requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=30
    )

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

        airline=out[0]["airline"]
        if not any(a in airline for a in AIRLINES_ALLOWED):
            continue

        def mins(x): return sum(l["duration"] for l in x)

        out_m=mins(out)
        in_m=mins(inc)
        total=out_m+in_m

        miles_label,val=miles_value_check(price,dest)

        if price<=SNIPER_PRICE:
            send_whatsapp(f"🚨 SNIPER ₹{price} to {dest}!")

        link=airline_link(airline,"DEL",dest,depart)

        score=deal_score(price,total,val)

        text=f"""
₹{price}
Airline: {airline}
Total Time: {total//60}h {total%60}m

Miles Value:
{miles_label}

Book:
{link}
"""

        found.append({"score":score,"text":text})

    return found

# ---------------- SCAN ----------------
def scan_all():

    ranked=[]
    d=DEPARTURE_START

    print("=== SCAN START ===")

    while d<=DEPARTURE_END:
        r=d+datetime.timedelta(days=RETURN_DAYS)

        for dest in DESTINATIONS:
            print(f"Checking {dest} | {d}")
            ranked+=search_flights(d,r,dest)

        d+=datetime.timedelta(days=1)

    ranked.sort(key=lambda x:x["score"])

    results=[x["text"] for x in ranked[:5]]

    print(f"Deals found: {len(results)}")

    return results

# ---------------- MAIN ----------------
if __name__=="__main__":

    if "runonce" in sys.argv:

        print("=== AD-HOC RUN ===")

        try:
            deals=scan_all()
            send_email(deals)

        except Exception as e:
            print("ERROR:",e)
            send_error_email(str(e))

    else:
        while True:

            try:
                deals=scan_all()
                send_email(deals)

            except Exception as e:
                send_error_email(str(e))

            print("Sleeping 8h...")
            time.sleep(28800)

