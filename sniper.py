import requests, os, datetime, time, json
from dotenv import load_dotenv

load_dotenv()

print("=== SNIPER MODE STARTED ===")

SERPAPI_KEY=os.getenv("SERPAPI_KEY")
SENDGRID_API_KEY=os.getenv("SENDGRID_API_KEY")
ALERT_EMAIL=os.getenv("ALERT_EMAIL")

DESTINATIONS=["LIS","OPO"]
CACHE_FILE="sniper_cache.json"

# ---------- Cache ----------
def load_cache():
    if os.path.exists(CACHE_FILE):
        return json.load(open(CACHE_FILE))
    return {}

def save_cache(c):
    json.dump(c,open(CACHE_FILE,"w"))

# ---------- Airline Links ----------
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

# ---------- Email ----------
def send_email(subject,body):

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

    print("EMAIL ALERT SENT")

# ---------- Mistake Detector ----------
def mistake_check(hist,price):

    if len(hist)<3:
        return None

    prices=[h["price"] for h in hist]
    avg=sum(prices)/len(prices)
    low=min(prices)
    last=prices[-1]

    if price<0.7*avg:
        return "🚨 30% BELOW AVERAGE"

    if price<0.85*low:
        return "🚨 BELOW HISTORICAL LOW"

    if price<130000:
        return "🚨 ULTRA LOW BUSINESS FARE"

    if last-price>25000:
        return "🚨 SUDDEN PRICE DROP"

    return None

# ---------- Scan ----------
def scan():

    print("SNIPER SCAN:",datetime.datetime.now())

    cache=load_cache()

    depart=datetime.date.today()+datetime.timedelta(days=30)
    ret=depart+datetime.timedelta(days=7)

    for dest in DESTINATIONS:

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

        data=requests.get(
            "https://serpapi.com/search.json",
            params=params
        ).json()

        for f in data.get("best_flights",[]):

            price=f.get("price",999999)
            if price>350000:
                continue

            airline=f["outbound_flights"][0]["airline"]
            link=airline_link(airline,"DEL",dest,depart)

            key=f"{dest}_{depart}"
            hist=cache.get(key,[])
            hist.append({"price":price})
            hist=hist[-20:]
            cache[key]=hist
            save_cache(cache)

            alert=mistake_check(hist,price)

            if alert:

                body=f"""
{alert}

₹{price} Business Class

Route:
DEL → {dest}

Airline:
{airline}

Book:
{link}

⚡ Act fast — mistake fares disappear quickly.
"""

                send_email("🚨 Mistake Fare Alert",body)

# ---------- Loop ----------
while True:

    try:
        scan()
    except Exception as e:
        print("Error:",e)

    print("Sleeping 2h...")
    time.sleep(7200)
