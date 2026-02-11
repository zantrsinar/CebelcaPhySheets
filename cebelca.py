#!/usr/bin/env python3
"""
🛡️ FIXED: JSONDecodeError + Error handling
Čebelca BIZ + Google Sheets A2 navzdol
"""

import requests
import gspread
from google.oauth2.service_account import Credentials
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import re
import time
from datetime import datetime
import os
import json

# 🎯 TVOJA KONFIGURACIJA
CEBELCA_API_KEY = "15442955Wt3sZwN4RnckxMyDrjO6JLlGeiqmgI8HQz5FTUChu2"
SHEET_ID = os.getenv('SHEET_ID', 'tvoj_google_sheets_id')  # ← NADOMESTI!
GMAIL_USER = "za.trsinar@gmail.com"
GMAIL_PASS = os.getenv('GMAIL_PASS', 'tvoj_app_password')  # ← NADOMESTI!

def safe_json(response):
    """🛡️ FIXED JSONDecodeError"""
    try:
        if response is None:
            return None
        response.raise_for_status()  # 4xx/5xx error
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ HTTP Error: {e}")
        print(f"Status: {response.status_code if response else 'No response'}")
        print(f"Text: {response.text[:200] if response else 'Empty'}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ JSON Error: {e}")
        print(f"Raw response: {response.text[:300] if response else 'Empty'}")
        return None

def test_google_sheets():
    """🧪 Test povezava + SHEET_ID"""
    print("🧪 Google Sheets test...")
    try:
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).worksheet("Sheet1")
        row1 = sheet.row_values(1)
        print(f"✅ Sheet1 OK: {row1[0] if row1 else 'Prazno'} | Rows: {len(sheet.get_all_values())}")
        return sheet
    except Exception as e:
        print(f"❌ Google Sheets napaka: {e}")
        print("🔧 FIX:")
        print("1. Ustvari credentials.json (Google Cloud)")
        print("2. Preveri SHEET_ID (dolgi niz iz URL)")
        print("3. Deli Sheet1 z service account email")
        return None

def test_cebelca_api():
    """🧪 Test Čebelca API"""
    print("🧪 Čebelca API test...")
    url = "https://www.cebelca.biz/API?_r=invoice&_m=list"
    headers = {'Authorization': f'Bearer {CEBELCA_API_KEY}', 'Content-Type': 'application/json'}
    response = requests.get(url, headers=headers, timeout=10)
    data = safe_json(response)
    print(f"✅ Čebelca API: {response.status_code} | Data: {data is not None}")
    return response.status_code == 200

def cebelca_api(url, method='POST', data=None):
    """🛡️ FIXED API z error handling"""
    headers = {'Authorization': f'Bearer {CEBELCA_API_KEY}', 'Content-Type': 'application/json'}
    try:
        if method == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=30)
        else:
            response = requests.get(url, headers=headers, timeout=30)
        return response
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None

def extract_id(text):
    """Izlušti ID iz HTML/JSON"""
    if not text:
        return None
    patterns = [r'id[:\s]*"?(\d+)', r'\[(\d+)\]', r'(\d{4,})']
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

def preveri_vse_vrstice(sheet):
    """🔍 A2 navzdol - SAFE"""
    print(f"\n⏰ {datetime.now()} - PREVERBA")
    vse_vrstice = sheet.get_all_values()
    
    obdelane = 0
    for row_idx, vrstica in enumerate(vse_vrstice[1:], start=2):
        if len(vrstica) < 2 or not vrstica[0]:
            break
        
        trigger1 = str(vrstica[0]).upper().strip()
        trigger2 = str(vrstica[1]).upper().strip() if len(vrstica) > 1 else ""
        
        print(f"Row {row_idx}: '{trigger1}' | '{trigger2}'")
        
        if trigger1 == "USTVARI":
            ustvari_predracun(sheet, row_idx)
            obdelane += 1
            time.sleep(3)  # Rate limit
        
        elif trigger2 == "POTRDI":
            potridi_racun(sheet, row_idx)
            obdelane += 1
            time.sleep(3)
    
    print(f"✅ Končano: {obdelane} vrstic")
    return obdelane

def ustvari_predracun(sheet, row):
    """🛡️ SAFE USTVARI"""
    vrstica = sheet.row_values(row)
    partner_id = int(vrstica[2] or 22)
    naziv = vrstica[3] or "Tango tečaj"
    kolicina = float(vrstica[4] or 1)
    enota = vrstica[5] or "kos"
    cena = float(vrstica[6] or 80)
    
    print(f"🚀 Row {row}: #{partner_id} {naziv}")
    
    url = "https://www.cebelca.biz/API?_r=invoice&_m=create"
    data = {
        "title": "", "doctype": 3, "partner_id": partner_id,
        "postavke": [{"naziv": naziv, "kolicina": kolicina, "enota_mere": enota, "cena": cena}]
    }
    
    response = cebelca_api(url, 'POST', data)
    if response and response.status_code == 200:
        invoice_id = extract_id(response.text)
        if invoice_id:
            sheet.update(f'H{row}', invoice_id)
            sheet.update(f'I{row}', f'✅ #{invoice_id}')
            sheet.update(f'A{row}', '')
            print(f"✅ Row {row}: #{invoice_id}")
            return True
    sheet.update(f'I{row}', f'❌ {response.status_code if response else "Timeout"}')
    return False

def potridi_racun(sheet, row):
    """🛡️ SAFE POTRDI"""
    vrstica = sheet.row_values(row)
    invoice_id = vrstica[7]
    if not invoice_id:
        sheet.update(f'I{row}', '❌ ID')
        return False
    
    url = "https://www.cebelca.biz/API?_r=invoice-sent&_m=finalize-invoice-2015"
    data = {"id": int(invoice_id), "doctype": 0}
    
    response = cebelca_api(url, 'POST', data)
    if response and response.status_code == 200:
        sheet.update(f'I{row}', f'✅ #{invoice_id}')
        sheet.update(f'B{row}', '')
        return True
    sheet.update(f'I{row}', f'❌ {response.status_code if response else "Error"}')
    return False

if __name__ == "__main__":
    print("🚀 Čebelca BIZ FIXED")
    
    # 🧪 TESTI
    if not test_cebelca_api():
        print("❌ Čebelca API napaka!")
        exit(1)
    
    sheet = test_google_sheets()
    if not sheet:
        print("❌ Google Sheets napaka!")
        exit(1)
    
    preveri_vse_vrstice(sheet)
