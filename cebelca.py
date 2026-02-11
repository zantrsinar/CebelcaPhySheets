#!/usr/bin/env python3
"""
🏆 Čebelca BIZ + Google Sheets - A2 NAVZDOL (več vrstic)
API: 15442955Wt3sZwN4RnckxMyDrjO6JLlGeiqmgI8HQz5FTUChu2
Gmail: za.trsinar@gmail.com
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

# 🎯 TVOJA KONFIGURACIJA
CEBELCA_API_KEY = "15442955Wt3sZwN4RnckxMyDrjO6JLlGeiqmgI8HQz5FTUChu2"
SHEET_ID = os.getenv('https://docs.google.com/spreadsheets/d/1KShr-adgEcGKAokmKDLZKZB-nw8mDLxQzwGkAJnNdTU/edit?gid=0#gid=0')  # NADOMESTI!
GMAIL_USER = "za.trsinar@gmail.com"
GMAIL_PASS = os.getenv('GMAIL_PASS', 'tvoj_app_password')  # NADOMESTI!

# Google Sheets (Sheet1)
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).worksheet("Sheet1")

def cebelca_api(url, method='POST', data=None):
    """Čebelca API klic"""
    headers = {'Authorization': f'Bearer {CEBELCA_API_KEY}', 'Content-Type': 'application/json'}
    try:
        if method == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=30)
        else:
            response = requests.get(url, headers=headers, timeout=30)
        print(f"API {method} {url.split('?_')[0]}: {response.status_code}")
        return response
    except Exception as e:
        print(f"❌ API napaka: {e}")
        return None

def extract_id(text):
    """Izlušti invoice ID"""
    patterns = [r'id[:\s]*"?(\d+)', r'\[(\d+)\]', r'(\d{4,})']
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None

def ustvari_predracun(row):
    """USTVARI trigger za vrstico"""
    print(f"🚀 USTVARI row {row}")
    vrstica = sheet.row_values(row)
    
    partner_id = int(vrstica[2]) if vrstica[2] else 22
    naziv = vrstica[3] or "Tango tečaj"
    kolicina = float(vrstica[4] or 1)
    enota = vrstica[5] or "kos"
    cena = float(vrstica[6] or 80)
    email = vrstica[9] or ""
    
    url = "https://www.cebelca.biz/API?_r=invoice&_m=create"
    data = {
        "title": "", "doctype": 3,
        "partner_id": partner_id,
        "postavke": [{"naziv": naziv, "kolicina": kolicina, "enota_mere": enota, "cena": cena}]
    }
    
    response = cebelca_api(url, 'POST', data)
    if response and response.status_code == 200:
        invoice_id = extract_id(response.text)
        if invoice_id:
            sheet.update(f'H{row}', invoice_id)
            sheet.update(f'I{row}', f'✅ PREDRAČUN #{invoice_id}')
            sheet.update(f'A{row}', '')
            print(f"✅ Row {row}: #{invoice_id}")
            
            if email:
                posli_pdf(invoice_id, email, "Predračun")
            return True
    sheet.update(f'I{row}', f'❌ API: {response.status_code if response else "Timeout"}')
    return False

def potridi_racun(row):
    """POTRDI trigger za vrstico"""
    print(f"💰 POTRDI row {row}")
    vrstica = sheet.row_values(row)
    invoice_id = vrstica[7]  # H stolpec
    
    if not invoice_id:
        sheet.update(f'I{row}', '❌ ID manjka')
        return False
    
    url = "https://www.cebelca.biz/API?_r=invoice-sent&_m=finalize-invoice-2015"
    data = {"id": int(invoice_id), "doctype": 0}
    
    response = cebelca_api(url, 'POST', data)
    if response and response.status_code == 200:
        email = vrstica[9]
        sheet.update(f'I{row}', f'✅ RAČUN #{invoice_id}')
        sheet.update(f'B{row}', '')
        print(f"✅ Row {row}: #{invoice_id} potrjen")
        
        if email:
            posli_pdf(invoice_id, email, "Račun")
        return True
    sheet.update(f'I{row}', f'❌ Finalize: {response.status_code if response else "Error"}')
    return False

def posli_pdf(invoice_id, email, tip):
    """PDF + email od za.trsinar@gmail.com"""
    print(f"📧 {tip} #{invoice_id} → {email}")
    pdf_url = f"https://www.cebelca.biz/API?_r=invoice&_m=get-pdf&id={invoice_id}"
    response = requests.get(pdf_url, headers={'Authorization': f'Bearer {CEBELCA_API_KEY}'})
    
    if response.status_code == 200:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = email
        msg['Subject'] = f"{tip} #{invoice_id}"
        msg.attach(MIMEText(f"V prilogi je vaš {tip.lower()}.\n\nza.trsinar@gmail.com"))
        
        part = MIMEBase('application', 'pdf')
        part.set_payload(response.content)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={tip}_{invoice_id}.pdf')
        msg.attach(part)
        
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASS)
            server.send_message(msg)
            server.quit()
            print(f"✅ Email poslan!")
        except Exception as e:
            print(f"❌ Email napaka: {e}")

def preveri_vse_vrstice():
    """🔍 PREVERI A2, A3, A4... navzdol (do prve prazne vrstice)"""
    print(f"\n⏰ {datetime.now().strftime('%H:%M:%S')} - PREVERBA A2 navzdol")
    
    # Get vse vrstice od 2 navzdol
    vse_vrstice = sheet.get_all_values()
    
    obdelane = 0
    for row_idx, vrstica in enumerate(vse_vrstice[1:], start=2):  # Začne pri vrstici 2
        if len(vrstica) < 2 or not vrstica[0]:  # Prazen A stolpec = konec
            print(f"🛑 Konec na vrstici {row_idx} (prazno)")
            break
        
        trigger1 = str(vrstica[0]).upper().strip() if vrstica[0] else ""
        trigger2 = str(vrstica[1]).upper().strip() if len(vrstica) > 1 and vrstica[1] else ""
        
        print(f"Row {row_idx}: A='{trigger1}' B='{trigger2}'")
        
        if trigger1 == "USTVARI":
            if ustvari_predracun(row_idx):
                obdelane += 1
                time.sleep(2)  # Rate limit
        
        elif trigger2 == "POTRDI":
            if potridi_racun(row_idx):
                obdelane += 1
                time.sleep(2)
    
    print(f"✅ Obdelanih vrstic: {obdelane}")
    return obdelane

def test_povezava():
    """🧪 Test"""
    print("🧪 TEST - Čebelca + Sheet1")
    response = cebelca_api("https://www.cebelca.biz/API?_r=invoice&_m=list")
    status = response.status_code if response else "No response"
    print(f"✅ Čebelca API: {status}")
    
    row1 = sheet.row_values(1)
    print(f"✅ Sheet1 glava: {row1[0] if row1 else 'OK'}")
    return status == 200

if __name__ == "__main__":
    if test_povezava():
        preveri_vse_vrstice()
    else:
        print("❌ Test failed!")
