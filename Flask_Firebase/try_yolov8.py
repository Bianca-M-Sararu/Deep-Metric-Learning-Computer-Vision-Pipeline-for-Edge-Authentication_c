import cv2
import numpy as np
import subprocess
import threading
import time
from flask import Flask, Response

app = Flask(__name__)
model = 'yolov8n.onnx' 

retea = cv2.dnn.readNetFromONNX(model)
retea.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
retea.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

INPUT_SIZE = 640                 
CONF_THRESH = 0.40               

cadru_pentru_ai = None
yolo_box_curent = None
reset_tracker = False
lock = threading.Lock()


def firul_detectie_yolo():
    global cadru_pentru_ai, yolo_box_curent, reset_tracker
    
    cadre_fara_fata = 0
    
    while True:
        img_analiza = None
        with lock:
            if cadru_pentru_ai is not None:
                img_analiza = cadru_pentru_ai.copy()
                cadru_pentru_ai = None

        if img_analiza is not None:
            h_img, w_img = img_analiza.shape[:2]
            imagine_pregatita = cv2.dnn.blobFromImage(img_analiza, 1/255.0, (INPUT_SIZE, INPUT_SIZE), swapRB=True, crop=False)
            retea.setInput(imagine_pregatita)
            
            try:
                iesiri = retea.forward()
                date = iesiri[0].transpose()
                
                fata_gasita = False
                
                for rand in date:
                    conf = float(rand[4])
                    if conf > CONF_THRESH:
                        xc, yc, w, h = rand[0], rand[1], rand[2], rand[3]
                        
                        scale_x = w_img / INPUT_SIZE
                        scale_y = h_img / INPUT_SIZE
                        
                        w_r = int(w * scale_x)
                        h_r = int(h * scale_y)
                        x_r = int((xc - w / 2) * scale_x)
                        y_r = int((yc - h / 2) * scale_y)

                        
                        w_final = int(w_r * 0.45)
                        h_final = int(h_r * 0.50)
                        x_final = int(x_r + (w_r * 0.27)) 
                        y_final = int(y_r + (h_r * 0.05))

                        
                        x_final = max(0, min(x_final, w_img - 10))
                        y_final = max(0, min(y_final, h_img - 10))
                        w_final = max(20, min(w_final, w_img - x_final))
                        h_final = max(20, min(h_final, h_img - y_final))
                        
                        with lock:
                            yolo_box_curent = (x_final, y_final, w_final, h_final)
                            reset_tracker = True 
                            
                        fata_gasita = True
                        cadre_fara_fata = 0
                        break 
                
                if not fata_gasita:
                    cadre_fara_fata += 1
                    if cadre_fara_fata > 3:
                        with lock:
                            yolo_box_curent = None
                            reset_tracker = True 
            
            except Exception as e:
                print(f"Eroare YOLO: {e}")

        time.sleep(0.01)

fir = threading.Thread(target=firul_detectie_yolo, daemon=True)
fir.start()

def genereaza_flux():
    global cadru_pentru_ai, yolo_box_curent, reset_tracker

    comanda = [
        'rpicam-vid', '-t', '0', '--inline', '--width', '800', '--height', '600',
        '--framerate', '25', '--codec', 'mjpeg', '-o', '-', '--flush'
    ]

    proces = subprocess.Popen(comanda, stdout=subprocess.PIPE, bufsize=10**6)
    bytes_data = bytes()
    cadru_nr = 0
    
    tracker = None
    tracker_activ = False
    cutie_de_desenat = None
    nume_tracker = "ACTIVE"

    try:
        while True:
            chunk = proces.stdout.read(8192)
            if not chunk: break

            bytes_data += chunk
            a = bytes_data.find(b'\xff\xd8')
            b = bytes_data.find(b'\xff\xd9')

            if a != -1 and b != -1:
                jpg = bytes_data[a:b+2]
                bytes_data = bytes_data[b+2:]

                cadru = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if cadru is None: continue

                if cadru_nr % 4 == 0:
                    with lock:
                        cadru_pentru_ai = cadru.copy()
                cadru_nr += 1

                with lock:
                    if reset_tracker:
                        if yolo_box_curent is not None:
                            if hasattr(cv2, 'legacy') and hasattr(cv2.legacy, 'TrackerMOSSE_create'):
                                tracker = cv2.legacy.TrackerMOSSE_create()
                                nume_tracker = "MOSSE"
                            elif hasattr(cv2, 'TrackerMOSSE_create'):
                                tracker = cv2.TrackerMOSSE_create()
                                nume_tracker = "MOSSE"
                            elif hasattr(cv2, 'legacy') and hasattr(cv2.legacy, 'TrackerKCF_create'):
                                tracker = cv2.legacy.TrackerKCF_create()
                                nume_tracker = "KCF"
                            elif hasattr(cv2, 'TrackerKCF_create'):
                                tracker = cv2.TrackerKCF_create()
                                nume_tracker = "KCF"
                            else:
                                tracker = cv2.TrackerMIL_create()
                                nume_tracker = "MIL"

                            tracker.init(cadru, yolo_box_curent)
                            tracker_activ = True
                            cutie_de_desenat = yolo_box_curent
                        else:
                            tracker = None
                            tracker_activ = False
                            cutie_de_desenat = None
                        
                        reset_tracker = False 

                if tracker_activ and tracker is not None:
                    ok, box = tracker.update(cadru)
                    if ok:
                        x, y, w, h = [int(v) for v in box]
                        cutie_de_desenat = (x, y, w, h)
                    else:
                        tracker_activ = False
                        cutie_de_desenat = None


                cadru_gri = cv2.cvtColor(cadru, cv2.COLOR_BGR2GRAY)
                

                cadru_fin = cv2.GaussianBlur(cadru_gri, (5, 5), 0)


                cadru_clar = cv2.convertScaleAbs(cadru_fin, alpha=1.3, beta=15)

              
                cadru = cv2.cvtColor(cadru_clar, cv2.COLOR_GRAY2BGR)

               
                if cutie_de_desenat is not None:
                    x, y, w, h = cutie_de_desenat
                    cv2.rectangle(cadru, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(cadru, f"TRACKING: {nume_tracker}", (x, max(20, y - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                _, jpeg_final = cv2.imencode('.jpg', cadru, [cv2.IMWRITE_JPEG_QUALITY, 85])
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + jpeg_final.tobytes() + b'\r\n')

    finally:
        proces.kill()

@app.route('/video_feed')
def video_feed():
    return Response(genereaza_flux(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True, debug=False)
