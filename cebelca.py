import requests
import gspread
from google.oauth2.service_account import Credentials
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Čebelca config
CEBELCA_API_KEY = "15442955Wt..."  # Tvoj ključ
SHEET_ID = "tvoj_google_sheets_id"  # Iz URL

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SHEET_ID).sheet1

def ustvari_predracun(partner_id, naziv, kolicina, enota, cena, email):
    """Ustvari predračun v Čebelci + email PDF"""
    
    # Čebelca API klic
    url = "https://www.cebelca.biz/API?_r=invoice&_m=create"
    headers = {
        "Authorization": f"Bearer {CEBELCA_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "title": "",
        "doctype": 3,  # predračun
        "partner_id": partner_id,
        "postavke": [{
            "naziv": naziv,
            "kolicina": kolicina,
            "enota_mere": enota,
            "cena": cena
        }]
    }
    
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code == 200:
        invoice_id = response.json().get('id')
        
        # Piši v Sheets
        sheet.update('H2', invoice_id)
        sheet.update('I2', f'✅ PREDRAČUN #{invoice_id}')
        sheet.update('A2', '')  # Počisti trigger
        
        # PDF + Email
        posji_pdf_email(invoice_id, email)
        return invoice_id
    else:
        sheet.update('I2', f'❌ API: {response.status_code}')
        return None

def posji_pdf_email(invoice_id, email):
    """Prenesi PDF + pošlji email"""
    pdf_url = f"https://www.cebelca.biz/API?_r=invoice&_m=get-pdf&id={invoice_id}"
    headers = {"Authorization": f"Bearer {CEBELCA_API_KEY}"}
    
    pdf_response = requests.get(pdf_url, headers=headers)
    if pdf_response.status_code == 200:
        # Email (Gmail SMTP)
        msg = MIMEMultipart()
        msg['From'] = 'tvoje@podjetje.si'
        msg['To'] = email
        msg['Subject'] = f'Predračun #{invoice_id}'
        
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_response.content)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename=Predracun_{invoice_id}.pdf')
        msg.attach(part)
        
        # Pošlji (prilagodi SMTP)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login('tvoje@podjetje.si', 'app_password')
        server.send_message(msg)
        server.quit()

def preveri_trigger():
    """Preveri če je A2=USTVARI ali B2=POTRDI"""
    vrstica2 = sheet.row_values(2)
    
    # USTVARI trigger
    if vrstica2[0].upper() == 'USTVARI':
        ustvari_predracun(
            partner_id=int(vrstica2[2]),  # C2
            naziv=vrstica2[3],            # D2
            kolicina=float(vrstica2[4]),  # E2
            enota=vrstica2[5],            # F2
            cena=float(vrstica2[6]),      # G2
            email=vrstica2[9]             # J2
        )
    
    # POTRDI trigger
    elif vrstica2[1].upper() == 'POTRDI':
        invoice_id = vrstica2[7]  # H2
        potridi_racun(invoice_id)

def potridi_racun(invoice_id):
    """Predračun → račun"""
    url = "https://www.cebelca.biz/API?_r=invoice-sent&_m=finalize-invoice-2015"
    data = {"id": int(invoice_id), "doctype": 0}
    headers = {"Authorization": f"Bearer {CEBELCA_API_KEY}", "Content-Type": "application/json"}
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        sheet.update('I2', f'✅ RAČUN #{invoice_id}')
        sheet.update('B2', '')  # Počisti trigger

if __name__ == "__main__":
    preveri_trigger()
