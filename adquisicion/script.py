# -*- coding: utf-8 -*-
"""
Created on Sun May 31 13:19:48 2026
@author: Agustin O. Umedez
Script para medir resistencia (multimetro via RS-232) y temperatura (termocupla via OCR) en paralelo
"""

import cv2
import subprocess
import matplotlib.pyplot as plt
import numpy as np
import time
import csv
import serial
from adquisicion.tools import generar_proximo_nombre


# --- Constantes --- #
# Constantes de configuración generales
SPAN = 5            # segundos
TOLERANCIA = 10     # número máximo de errores seguidos antes de detener el programa
PRECISION = 5       # cantidad de veces que lee para promediar
# Constantes de ruteo
RUTA_SSOCR = "ssocr"
IMG_TEMP = "temp_crop.png" # Valor predeterminado
ARCHIVO_DESTINO = {
    "directorio":   "DATA",
    "descripcion":  "ejemplo",
    "prefijo":      "me_",
    "extension":    ".csv"
}
ROOT_DESTINO = generar_proximo_nombre(**ARCHIVO_DESTINO)
# Constantes de configuración para el multímetro
PUERTO_UJT = 'COM1'
BAUD_RATE = 9600
TIMEOUT = 2         # Timeout generoso

# --- Configuración del puerto --- #
multimetro_UJT = serial.Serial(
    port=PUERTO_UJT,
    baudrate=BAUD_RATE,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=TIMEOUT
)
# Líneas de control para habilitar el puerto en equipos viejos
multimetro_UJT.dtr = True
multimetro_UJT.rts = True

def leer_pantalla_lcd(imagen_recortada, nombre_temp="temp_crop.png"):
    """
    Guarda el recorte de OpenCV temporalmente y utiliza ssocr para leerlo.
    """
    alto, ancho = imagen_recortada.shape[:2]
    alpha = 0.01            # Factor de "shear"
    dx = abs(alpha) * alto  # Margen de seguridad para no cortar el número al inclinarlo
    
    # Matriz de Transformación Afín
    M = np.float32([
        [1, alpha, dx],
        [0, 1, 0]
    ])
    
    # Aplicamos el "shear"
    enderezada = cv2.warpAffine(
        imagen_recortada, 
        M, 
        (ancho + int(dx), alto), 
        borderMode=cv2.BORDER_REPLICATE
    )

    # Ampliar la imagen (Escalado cúbico)
    frame_ampliado = cv2.resize(enderezada, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

    # Convertir a escala de grises
    gris = cv2.cvtColor(frame_ampliado, cv2.COLOR_BGR2GRAY)
    
    # Suavizado (Gaussian Blur) - Reducido para no borrar el punto
    blur = cv2.GaussianBlur(gris, (5, 5), 0)

    # Guardar el recorte de OpenCV en el disco para que ssocr pueda leerlo
    cv2.imwrite(nombre_temp, blur)
    
    # Configuración de parámetros de SSOCR
    comando = [
        "wsl",          # Usar "Windows Subsystem for Linux" o WSL
        RUTA_SSOCR,
        "-d", "-1",     # Detectar cantidad automática de dígitos
        "-c", "digit",  # Restringir a caracteres numéricos
        "-r", "5.5",    # Height to Width ratio (H/W) del dígito 1
        "-C",           # Ignorar puntos decimales
        # "-T",           # Usar umbral adaptativo (Iterative Thresholding)
        "-M", "5x40",   # Dimensiones mínimas de un potencial dígito
        "-t", "45",     # Umbral estricto manual (mayor -t, menos estricto)
        "-D",           # Guardar imagen de diagnóstico
        nombre_temp
    ]
    
    try:
        # Ejecutar SSOCR y capturar la salida
        resultado = subprocess.run(
            comando, 
            capture_output=True, 
            text=True, 
            check=True
        )
        # Limpiar espacios o saltos de línea de la lectura
        lectura = resultado.stdout.strip()
        # Convertir la lectura a un dato de tipo int, esto levanta un ValueError si falla
        lectura_final = int(lectura)
        if (lectura_final*10<1500): return lectura_final / 10 # Por encima de los 150°C, la termocupla deja de mostrar el dígito decimal
        else: lectura_final
        
    except subprocess.CalledProcessError as e:
        print(f"Error al leer la imagen. Código: {e.returncode}")
        # stderr suele contener pistas sobre si la imagen era muy oscura/clara
        print(f"Detalle: {e.stderr}")
        return None
    except FileNotFoundError:
        print("¡Error! No se encontró el ejecutable de ssocr en el sistema.")
        return None
    except ValueError:
        print("Error al leer la imagen, no es un número:", lectura)
        return None

def graficar_ultima_medicion(frame, nombre_temp, contador):
    """
    Grafica la última medición realiza. Notar que solo se almacena la última lectura,
    esto sirve estrictamente como referencia y no contempla las mediciones intermedias.

    La imagen superior es el frame utilizado como input para el algoritmo ssocr.
    La imagen inferior (diagnóstico) sirve para corroborar que el algoritmo ssocr está leyendo adecuadamente la imagen,
    allí se verán las lineas creadas por el algoritmo para delimitar cada dígito.
    """
    fig, (ax1, ax2) = plt.subplots(2, 1)
                            
    ax1.imshow(frame)
    ax2.imshow(cv2.imread(nombre_temp))
    
    ax1.tick_params(left=False, right=False, labelleft=False,
        bottom=False, top=False, labelbottom=False)
    ax2.tick_params(left=False, right=False, labelleft=False, 
        bottom=False, top=False, labelbottom=False)
    
    fig.suptitle(f"Medición nº {contador}")
    fig.tight_layout()
    fig.savefig(generar_proximo_nombre(
        ARCHIVO_DESTINO["directorio"]+r"/imgs/"+ARCHIVO_DESTINO["descripcion"], "", ARCHIVO_DESTINO["prefijo"], ".jpg"
        # Ej: "DATA/imgs/ejemplo/me_0.jpg", luego "DATA/imgs/ejemplo/me_1.jpg", etc
    ))
    plt.close()

def configurar_instrumentos():    
    print("Estableciendo conexión remota...")
    # FORZAR MODO REMOTO (Soluciona el error +550)
    multimetro_UJT.write(b'SYST:REM\r\n')
    time.sleep(0.2)
    
    # LIMPIAR ERRORES PREVIOS
    multimetro_UJT.write(b'*CLS\r\n')
    time.sleep(0.1)
    
    # RESET Y CONFIGURACIÓN
    print("Configurando rango fijo de 10kOhm...")
    multimetro_UJT.write(b'*RST\r\n')
    time.sleep(0.1)
    multimetro_UJT.write(b'CONF:RES 10000\r\n') # Rango fijo 10kOhm
    
    # VELOCIDAD DE MUESTREO (NPLC)
    # 1 NPLC es el balance justo para 0.5s de intervalo.
    multimetro_UJT.write(b'SENSE:RES:NPLC 1\r\n')
    
    time.sleep(0.5)
    print("Instrumentos listos y en modo Rmt.")

def cerrar_puerto():
    # Liberar la cámara y cerrar todas las ventanas de OpenCV
    cap.release()
    cv2.destroyAllWindows()

    # Cerrar puerto serie
    multimetro_UJT.write(b'DISP:TEXT:STAT OFF\r\n') # Vuelve a mostrar mediciones normales
    multimetro_UJT.write(b'SYST:LOC\r\n')           # Devuelve el control al panel frontal
    multimetro_UJT.close()                          # Cerramos el puerto
    
    print("Puertos cerrados con éxito.")

def main():
    print("Iniciando configuración de hardware...")
    configurar_instrumentos()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("No se pudo conectar a la cámara.")
        cerrar_puerto()
        return

    print("Presiona CTRL+C para detener la medición.")
    t_inicio = time.perf_counter()
    contador = 0
    try:
        # Preparamos archivo CSV donde se almacenarán los datos
        with open(ROOT_DESTINO, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Tiempo [s]", "Temperatura_OCR [C]", "Resistencia_UJT [Ohm]"])
            
            while True:
                t_rel = time.perf_counter() - t_inicio
                
                if t_rel >= SPAN:
                    lecturas_OCR, lecturas_MM_UJT = [], []
                    err_ocr, err_mm = 0, 0
                    i = 0
                    while (i < PRECISION) and (err_ocr < TOLERANCIA) and (err_mm < TOLERANCIA):
                        # Leer el fotograma actual
                        ret, frame = cap.read()
                        if not ret:
                            print("No se pudo recibir el fotograma.")
                            err_ocr += 1
                            continue

                        # Recorte donde solo se ve el display de la termocupla
                        crop = frame[180:267, :217] # [y1:y2, x1:x2]
                        lectura_display = leer_pantalla_lcd(crop, IMG_TEMP) # grados celcius

                        # Pedir lectura del Multímetro
                        multimetro_UJT.write(b'READ?\r\n')
                        linea_multimetro_UJT = multimetro_UJT.readline().decode('ascii').strip() # Ohm
                        
                        if not linea_multimetro_UJT:
                            print("Timeout: El multímetro (UJT) no respondió a tiempo.")
                            err_mm += 1
                            continue
                        if not lectura_display:
                            cv2.imwrite(generar_proximo_nombre(
                                "FALLOS", prefijo="fallo_", extension=".png"
                            ), crop)
                            print("Error: No se registró la lectura de la termocupla.")
                            err_ocr += 1
                            continue
                        else:
                            lecturas_MM_UJT.append( float(linea_multimetro_UJT) )
                            lecturas_OCR.append( lectura_display )
                            i += 1
                    
                    # Si no se leyeron bien varios fotogramas seguidos, salir del bucle
                    if err_ocr >= TOLERANCIA:
                        raise RuntimeError(f"(SSOCR) Se alcanzó el límite de tolerancia: {err_ocr} errores consecutivos.")
                    if err_mm >= TOLERANCIA:
                        raise RuntimeError(f"(SSOCR) Se alcanzó el límite de tolerancia: {err_mm} errores consecutivos.")

                    lect_final_OCR = np.mean(lecturas_OCR)
                    lect_final_MM_UJT = np.mean(lecturas_MM_UJT)

                    writer.writerow([f"{t_inicio:.3f}", lect_final_OCR, lect_final_MM_UJT])
                    file.flush()
                    print(f"[{t_inicio:6.3f}(s)]  T: {lect_final_OCR:.2f}(C),  R: {lect_final_MM_UJT:.2f}(Ohm)")
            
                    graficar_ultima_medicion(frame, IMG_TEMP, contador)

                    t_inicio += ((time.perf_counter() - t_inicio) + t_rel)/2
                    contador += 1
        
    except KeyboardInterrupt:
        print("Todo correcto.")

    except Exception as e:
        print(f"Error en el sistema: {e}")
    
    finally:
        print(f"Mediciones guardadas en --- {ROOT_DESTINO} ---")
        cerrar_puerto()

# --- Ejecución del código --- #
if __name__ == "__main__":
    main()

        
