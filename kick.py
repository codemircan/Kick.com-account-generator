import random, json, websocket, time, os, sys, console, re
import os
from kasada import salamoonder
import tls_client
from bs4 import BeautifulSoup as bs
import traceback
import requests
import json
import sys
import time
import queue
import random
import string
import threading
import imaplib
import email
import re
from datetime import datetime, timedelta

def random_string(length=5, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choices(chars, k=length))

def random_username():
    return f"{random_string(random.randint(7, 10), string.ascii_lowercase)}_{random_string(random.randint(7, 10), string.ascii_lowercase)}{random.randint(10, 9999)}"

def random_password():
    return ''.join(random.sample(
        random.choice(string.ascii_uppercase) + random.choice(string.ascii_lowercase) +
        random.choice(string.digits) + random.choice("!@#^") +
        ''.join(random.choices(string.ascii_letters + string.digits + "!@#^", k=8)), random.randint(8, 12)
    ))

def last_chrome_version():
    return requests.get("https://api.sockets.lol/browsers").json()["chrome"]
def hc(c):
    headersCookies = ""
    for name, value in c.cookies.items():
        headersCookies = headersCookies + f"{name}={value}; "
    return headersCookies[:-2]

def get_verification_code_from_local_email(email_address, password):
    if "@hotmail.com" in email_address or "@outlook.com" in email_address:
        imap_server = "imap-mail.outlook.com"
    else:
        raise Exception("Unsupported email domain for local mail type")

    try:
        mail = imaplib.IMAP4_SSL(imap_server, 993)
        mail.login(email_address, password)
        mail.select("inbox")
    except imaplib.IMAP4.error as e:
        console.error(f"IMAP login failed for {email_address}: {e}")
        os._exit(1)

    # Search for emails from noreply@email.kick.com
    result, data = mail.search(None, '(UNSEEN FROM "noreply@email.kick.com")')
    if not data[0]:
        mail.logout()
        return None # No email from kick.com

    # Get the latest email
    latest_email_id = data[0].split()[-1]
    result, data = mail.fetch(latest_email_id, "(RFC822)")
    raw_email = data[0][1]

    msg = email.message_from_bytes(raw_email)

    # Find the verification code in the email body
    p = r'\\b\\d{6}\\b'
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            body = part.get_payload(decode=True).decode()
            codes = re.findall(p, body)
            if codes:
                mail.logout()
                return codes[0]
        elif part.get_content_type() == "text/html":
            body = part.get_payload(decode=True).decode()
            soup = bs(body, "html.parser")
            text = soup.get_text()
            codes = re.findall(p, text)
            if codes:
                mail.logout()
                return codes[0]
    mail.logout()
    return None

config = json.load(open("config.json"))

email_queue = queue.Queue()
file_lock = threading.Lock()
if config["mailType"] == "local":
    if not os.path.exists("email.txt"):
        console.error("email.txt not found")
        sys.exit()
    with open("email.txt", "r") as f:
        for line in f:
            email, password = line.strip().split(":")
            email_queue.put((email, password))

def create_account(password=None, username=None, chromeVersion=last_chrome_version()):
    try:
        username = random_username()
        emailType = config["mailType"]
        if emailType == "local":
            email, password = email_queue.get()
        else:
            raise Exception("Unsupported mailType. Please set mailType to 'local' in config.json")

        console.info(f"Using {email} | Username {username}")
        proxy = random.choice(open("proxies.txt").readlines()).strip()
        client = tls_client.Session(client_identifier="chrome_120", random_tls_extension_order=True)
        client.proxies = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
        client.headers = {
            "user-agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chromeVersion}.0.0.0 Safari/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9",
        }
        client.get("https://kick.com/")
        x = client.get("https://kick.com/sanctum/csrf")
        if x.status_code != 200:
            return create_account()
        xsrf = client.cookies["XSRF-TOKEN"].replace("%3D", "=")

        console.info(f"Got XSRF token")

        s = time.time()
        kasada = salamoonder()
        console.info(f"Solved kasada in {time.time()-s:.2f}s")
        client.headers.update({
            "authorization": f"Bearer {xsrf}",
            "x-xsrf-token": xsrf,
            "x-kpsdk-ct": kasada["x-kpsdk-ct"],
            "x-kpsdk-v": "j-0.0.0",
            "x-kpsdk-cd": kasada["x-kpsdk-cd"],
        })
        r = client.post("https://kick.com/api/v1/signup/send/email", json={"email": email})
        if r.status_code != 204:
            return False
        s = time.time()
        console.info(f"Waiting for verification code...")
        code = get_verification_code_from_local_email(email, password)
        console.info(f"Got verification code {code} in {time.time()-s:.2f}s")
        r = client.post("https://kick.com/api/v1/signup/verify/code", json={"email": email, "code": code})
        if r.status_code != 204:
            return False
        ktp = client.get("https://kick.com/kick-token-provider").json()
        r = client.post('https://kick.com/register', json={
            "email": email,
            "birthdate": (datetime.today() - timedelta(days=365 * random.randint(18, 40))).strftime("%m/%d/%Y"),
            "username": username,
            "password": password,
            "newsletter_subscribed": False,
            ktp["nameFieldName"]: "",
            "_kick_token_valid_from": ktp["encryptedValidFrom"],
            "agreed_to_terms": True,
            "cf_captcha_token": "",
            "enable_sms_promo": False,
            "enable_sms_security": False,
            "password_confirmation": password,
            "isMobileRequest": True
        })
        if r.status_code != 200:
            console.error(f"Failed to register: {r.status_code}")
            return False
        token = r.json().get("token")
        if not token:
            console.error("Failed to register token")
            return False
        with open("kick_accounts.txt", "a") as f:
            f.write(f"{email}:{password}:{username}:{token}\\n")
        with file_lock:
            with open("used_emails.txt", "a") as f:
                f.write(f"{email}:{password}\\n")

            with open("email.txt", "r") as f:
                lines = f.readlines()
            with open("email.txt", "w") as f:
                for line in lines:
                    if line.strip().split(":")[0] != email:
                        f.write(line)

        return token
    except Exception:
        traceback.print_exc()
        return False
