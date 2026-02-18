import requests
import pandas as pd
import datetime
import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv("config.env")

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

def search_flights(depart_date, return_date, destination):
    url = "https://serpapi.com/search.json"

    params = {
        "engine": "google_flights",
        "departure_id": "DEL",
        "arrival_id": destination,
        "outbound_date": depart_date,
        "return_date": return_date,
        "currency": "INR",
        "hl": "en",
        "travel_class": "2",
        "deep_search": "true",
        "api_key": SERPAPI_KEY
    }

    try:
        r = requests.get(url, params=params, verify=False, timeout=60)
        data = r.json()

        flights = []
        if "best_flights" in data:
            for f in data["best_flights"]:
                price = f.get("price", 999999)
                airline = f["flights"][0]["airline"]
                flights.append({
                    "price": price,
                    "airline": airline,
                    "route": destination,
                    "depart": depart_date,
                    "return": return_date
                })

        return flights

    except Exception as e:
        print("API error:", e)
        return []

def send_email(deals):
    if not deals:
        print("No cheap deals today")
        return

    body = ""
    for d in deals:
        body += f"""
Route: Delhi → {d['route']}
Airline: {d['airline']}
Price: ₹{d['price']}
Depart: {d['depart']}
Return: {d['return']}
-------------------------
"""

    msg = MIMEMultipart()
    msg["Subject"] = "🔥 Portugal Flight Deals Found"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(EMAIL_SENDER, EMAIL_PASS)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

    print("Email sent!")

def scan_all():
    print("Starting GOD MODE scan...")

    base_depart = datetime.date(2026, 7, 25)
    deals = []

    for i in range(6):
        depart = base_depart + datetime.timedelta(days=i)
        ret = depart + datetime.timedelta(days=7)

        depart_str = depart.strftime("%Y-%m-%d")
        ret_str = ret.strftime("%Y-%m-%d")

        for dest in ["LIS", "OPO"]:
            print(f"Checking {dest} | Depart {depart_str}")
            flights = search_flights(depart_str, ret_str, dest)

            for f in flights:
                if f["price"] < 200000:
                    deals.append(f)

    return deals

if __name__ == "__main__":
    results = scan_all()
    send_email(results)
