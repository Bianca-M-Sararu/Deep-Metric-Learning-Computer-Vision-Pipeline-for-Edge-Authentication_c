import cv2
import os

def enhance_to_high_res(input_path, output_path, model_path):
    if not os.path.exists(input_path):
        print("Imaginea de intrare nu a fost găsită.")
        return

    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    
    sr.readModel(model_path)
    sr.setModel("edsr", 4) # Mărește rezoluția de 4 ori

    img = cv2.imread(input_path)
    
    print("Se procesează... poate dura câteva secunde.")
    result = sr.upsample(img)

    cv2.imwrite(output_path, result)
    print(f"Imaginea de înaltă definiție este aici: {output_path}")


cale_foto = "/new/image/load1.png"
cale_finala = "/new/image/load1_HD.png"
cale_model = "EDSR_x4.pb" 

enhance_to_high_res(cale_foto, cale_finala, cale_model)
