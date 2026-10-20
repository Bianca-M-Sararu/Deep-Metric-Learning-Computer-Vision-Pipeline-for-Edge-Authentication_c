import face_recognition                                                   
import cv2
import pickle
import numpy as np
import os
import threading
import subprocess
import time
import firebase_admin
from firebase_admin import credentials, firestore, storage
from flask import Flask, Response, jsonify
from mfrc522 import SimpleMFRC522                                          
from RPLCD.i2c import CharLCD                                              
import RPi.GPIO as GPIO                                                     



pin_releu = 18
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin_releu, GPIO.IN) 

cititor_rfid = SimpleMFRC522()
lcd_text_linia1 = "Sistem pornit"
lcd_text_linia2 = "Asteapta"

try:
    lcd = CharLCD('PCF8574', 0x20)
    lcd.clear()
except:
    lcd = None

def text_lcd(l1, l2=""):
    global lcd_text_linia1, lcd_text_linia2
    lcd_text_linia1, lcd_text_linia2 = l1, l2
    if lcd:
        lcd.clear()
        lcd.write_string(f"{l1[:16]}\r\n{l2[:16]}")
    print(f"[LCD] {l1} | {l2}")

#Flask

app = Flask(__name__)

if not firebase_admin._apps:
    credentiale = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(credentiale,{'storageBucket':'***.app'})

bd = firestore.client()
galeata = storage.bucket()
fete_cunoscute,nume_cunoscute,utilizatori_detalii = [],[],{}
blocare = threading.Lock()
nume_detectat = None
pauza = False 

def sincronizarea_datelor():
    global fete_cunoscute, nume_cunoscute, utilizatori_detalii
    print("\n Se sincronizează datele din cloud")
    
    if not os.path.exists('poze_cloud_temp'):
        os.makedirs('poze_cloud_temp')
    if not os.path.exists('encodings_cache'):
        os.makedirs('encodings_cache')

    utilizatori_ref = bd.collection('users').stream()
    contor = 0
    
    for document in utilizatori_ref:
        date = document.to_dict()
        id_user = document.id
        prenume = date.get('first_name', 'Necunoscut')
        nume_familie = date.get('last_name','') 
        nume_complet = f"{prenume}{nume_familie}".strip()
        rfid_cloud = str(date.get('rfid_tag', '')).strip()

    
        
        cale_cache = f'encodings_cache/{id_user}.pkl'
        cale_locala = f'poze_cloud_temp/{id_user}.jpg'
        
        try:
            if os.path.exists(cale_cache):
                with open(cale_cache, 'rb') as fisier:
                    codarea_fetei = pickle.load(fisier)
                with blocare:
                    fete_cunoscute.append(codarea_fetei)
                    nume_cunoscute.append(id_user)
                    utilizatori_detalii[id_user] = {'nume_complet': nume_complet,
                                                    'prenume' : prenume,
                                                    'rfid': rfid_cloud}
                    
                contor += 1
                print(f" Se încarcă din memoria cache: {id_user}")
            else:
                nume_fisier = f'faces/{id_user}.jpg'
                referinta = galeata.blob(nume_fisier)
                
                if referinta.exists():
                    referinta.download_to_filename(cale_locala)
                    img = face_recognition.load_image_file(cale_locala)
                    img_gri = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                    img_ai = cv2.cvtColor(img_gri, cv2.COLOR_GRAY2RGB)
                    vectori_fata = face_recognition.face_encodings(img_ai)
                    
                    if len(vectori_fata) > 0:
                        vector = vectori_fata[0]
                        with open(cale_cache, 'wb') as fisier:
                            pickle.dump(vector,fisier)
                        with blocare:
                            fete_cunoscute.append(vector)
                            nume_cunoscute.append(id_user)
                            utilizatori_detalii[id_user] = {'nume_complet': nume_complet,
                                                            'prenume' : prenume,
                                                            'rfid': rfid_cloud}
                        contor += 1
                        print(f" S-a finalizat descărcarea persoanei curente: {prenume}")
        except Exception as exceptie:  
            print(f" S-a depistat o eroare la rularea codului {prenume}: {exceptie}")      
    return contor > 0

def salveaza_log(nume, status, mesaj, cod_eroare=""):
    try:
        bd.collection('access_logs').add({
            'nume':nume,
            'status':status,
            'mesaj':mesaj,
            'cod_eroare':cod_eroare,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
    except Exception as exceptie: 
        print(f"Există o eroare in logare: {exceptie}")

# Yala
def deschide_yala(nume):
    global pauza
    pauza = True 
    print(f"Usa se deschide, {nume}")
    
    GPIO.setup(pin_releu, GPIO.OUT)
    GPIO.output(pin_releu, GPIO.LOW) 
    
    for i in range(15, 0, -1):
        text_lcd("Acces PERMIS", f"Inchidere: {i}s")
        time.sleep(1)
    
    GPIO.setup(pin_releu, GPIO.IN)
    text_lcd("Usa inchisa", "Resetare sistem")
    time.sleep(2)
    pauza = False

def gestionare_cazuri_FSM():
    global nume_detectat, pauza
    stare = "IDLE"
    timp_start = 0
    istoric = []
    nume_blocat = None

    while True:
        if pauza:
            time.sleep(0.5)
            stare = "IDLE"
            continue

        time.sleep(0.1)
        nume_camera = nume_detectat

        if stare == "IDLE" and nume_camera:
            stare = "DETECTING"
            timp_start = time.time()
            text_lcd("Sistem pornit:","Asteapta ")
        elif stare == "DETECTING":
            if not nume_camera: 
                stare = "IDLE"
                text_lcd("Detectare:","Te rog asteapta")
            elif time.time()-timp_start >= 3:
                stare = "RECOGNIZING"
                timp_start = time.time()
                istoric = []
                text_lcd("Recunoastere:","Te rog asteapta")
        elif stare == "RECOGNIZING":
            if nume_camera: 
                istoric.append(nume_camera)
            if time.time()-timp_start >= 5:
                if not istoric: 
                    stare = "IDLE"
                    continue
                nume_frecvent = max(set(istoric),key=istoric.count)
                if nume_frecvent == "Necunoscut":
                    text_lcd("Acces respins","Necunoscut")
                    salveaza_log("Necunoscut","NEPERMIS","Persoana necunoscuta","ERR_UNKNOWN_FACE")
                    timp_pornire = time.time()
                    while time.time()-timp_pornire < 6: time.sleep(0.1)
                    stare = "IDLE"
                    text_lcd("Sistem pornit","Te rog asteapta")
                else:
                    nume_blocat = nume_frecvent
                    text_lcd(f"{nume_blocat}", "Apropie cardul")
                    stare = "WAITING_RFID"
                    timp_start = time.time()
        elif stare == "WAITING_RFID":
            id_card, _ = cititor_rfid.read_no_block()
            if id_card:
                id_card = str(id_card).strip()
                if id_card == utilizatori_detalii[nume_blocat]['rfid']:
                    salveaza_log(nume_blocat, "PERMIS", "Acces autorizat", "OK")
                    deschide_yala(nume_blocat)
                    stare = "IDLE"
                else:
                    text_lcd("Card GRESIT", "Acces RESPINS")
                    salveaza_log(nume_blocat, "NEPERMIS","RFID gresit","ERR_RFID_MISMATCH")
                    timp_pornire = time.time()
                    while time.time()-timp_pornire < 6: time.sleep(0.1)
                    stare = "IDLE"
                    text_lcd("Sistem pornit", "Te rog asteapta")
            elif time.time()-timp_start >= 10:
                text_lcd("Timpul a expirat", "Reluare in 6s")
                salveaza_log(nume_blocat, "NEPERMIS","Timeout RFID","ERR_TIMEOUT_RFID")
                timp_pornire = time.time()
                while time.time()-timp_pornire < 6: time.sleep(0.1)
                stare = "IDLE"
                nume_blocat = None
                text_lcd("Sistem pornit", "Te rog asteapta")

def genereaza_flux():
    global nume_detectat
    comanda = ['rpicam-vid','-t','0','--inline','--width','800','--height','600','--framerate','12','--codec','mjpeg','-o','-','--flush']
    proces = subprocess.Popen(comanda, stdout=subprocess.PIPE, bufsize=10**6)
    date_B = bytes()
    contor_cadre = 0
    locatii_fete, nume_fete_cadru = [], []
    try:
        while True:
            parte_flux_citit = proces.stdout.read(8192)
            if not parte_flux_citit:
                break
            date_B =date_B+parte_flux_citit
            limita_inf = date_B.find(b'\xff\xd8')
            limita_sup = date_B.find(b'\xff\xd9')
            if limita_inf != -1 and limita_sup != -1:
                jpg = date_B[limita_inf:limita_sup+2]
                date_B = date_B[limita_sup+2:]
                incadrare = cv2.imdecode(np.frombuffer(jpg,dtype=np.uint8),cv2.IMREAD_COLOR)
                if incadrare is None:
                    continue
                contor_cadre += 1
                if contor_cadre % 6 == 0:
                    micsorare_cadru = cv2.resize(incadrare,(0,0),fx=0.25,fy=0.25)
                    rgb_micsorare_cadru = cv2.cvtColor(cv2.cvtColor(micsorare_cadru,cv2.COLOR_BGR2GRAY),cv2.COLOR_GRAY2RGB)
                    locatii_fete = face_recognition.face_locations(rgb_micsorare_cadru)
                    vectori_fata = face_recognition.face_encodings(rgb_micsorare_cadru,locatii_fete)
                    nume_fete_cadru = []
                    for vector in vectori_fata:
                        lista_comparatie = face_recognition.compare_faces(fete_cunoscute, vector, 0.5)
                        if True in lista_comparatie:
                            nume_recunoscut=nume_cunoscute[lista_comparatie.index(True)]
                        else:
                            nume_recunoscut="Necunoscut"
                        nume_fete_cadru.append(nume_recunoscut)

                    if nume_fete_cadru:
                        nume_detectat= nume_fete_cadru[0]
                    else:
                        nume_detectat= None
                
                incadrare_final = cv2.cvtColor(cv2.cvtColor(incadrare, cv2.COLOR_BGR2GRAY),cv2.COLOR_GRAY2BGR)
                for (p_sus,p_dreapta,p_jos,p_stanga),nume in zip(locatii_fete,nume_fete_cadru):
                    p_sus=p_sus*4
                    p_dreapta=p_dreapta*4
                    p_jos=p_jos*4
                    p_stanga=p_stanga*4

                    if nume == "Necunoscut":
                        culoare_rama =  (0,0,255)
                    else:
                        culoare_rama =  (0,255,0)

                    cv2.rectangle(incadrare_final,(p_stanga,p_sus),(p_dreapta,p_jos),culoare_rama,3)
                    cv2.putText(incadrare_final, nume, (p_stanga,p_sus-15),0,1.0,culoare_rama,3)
                _, buffer = cv2.imencode('.jpg', incadrare_final)
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    finally: proces.terminate()

@app.route('/video_feed')
@app.route('/livecam')
def livecam():
    return Response(genereaza_flux(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/lcd_status')
def lcd_status():
    global lcd_text_linia1, lcd_text_linia2
    return jsonify({"line1":lcd_text_linia1, "line2":lcd_text_linia2})

if __name__ == '__main__':
    if sincronizarea_datelor():
        threading.Thread(target=gestionare_cazuri_FSM, daemon=True).start()
        app.run(host='0.0.0.0', port=8080, threaded=True)
