# TP 3 - Física Experimental 2: Conductividad en Semiconductores y Cálculo del Band Gap

Este repositorio contiene los scripts de adquisición de datos, análisis numérico y el informe final correspondientes al Trabajo Práctico 3 de la asignatura. El objetivo principal de este experimento es caracterizar el comportamiento de la resistencia eléctrica en función de la temperatura para un transistor UJT y estimar la brecha de energía o *band gap* ($E_g$) del semiconductor en su región intrínseca.

## Estructura del Repositorio

```text
├── datos/                      # DataFrames limpios tras corregir lecturas del OCR y unificar escalas.
├── aquisicion/          
│   ├── script.py               # Script de recolección de datos en tiempo real (RS-232 y OCR).
│   └── tools.py                # Herramientas para facilitar nombramiento continuo de los archivos con mediciones.
├── analisis/                   
│   ├── auxiliar/               # Herramientas para facilitar el procesamiento de las incertidumbres.
│   │   ├── HP34401A.json       
│   │   └── instruments.py      
│   ├── AnalisisDatos.py        # Script de análisis, desdoblamiento de curvas y cálculo de regresiones.
│   └── analysis.py             # Herramientas para facilitar el procesamiento de las incertidumbres.
└── documentacion/             
    └── informe.pdf      
```

## Cómo Recrear el Experimento

Para un usuario que desee reproducir las mediciones o auditar el procesamiento de datos, el flujo de trabajo se divide en dos etapas:

### 1. Adquisición de Datos (`adquisicion/script.py`)

Para ejecutar este script en un entorno físico, es necesario configurar dos instrumentos en simultáneo:

* **Multímetro HP 34401A (Resistencia):** Se comunica vía cable RS-232 Null Modem utilizando la librería `pyserial`. Es de vital importancia configurar el panel frontal del equipo en **9600 BAUD, 8 BITS, PARITY NONE**.
* **Termocupla Cole-Parmer (Temperatura):** Dado que carece de salida de datos directa, se captura en video utilizando un teléfono como cámara web IP mediante **DroidCam**. El script aísla visualmente la pantalla principal del instrumento y aplica Reconocimiento Óptico de Caracteres (OCR) con ssocr para extraer el valor numérico en vivo. Los parámetros para recortar la imágen a la zona de interés deben ser colocados manualmente; para ello, se recomienda armar un script por separado para calibrar este algoritmo previo a las mediciones reales.

### 2. Procesamiento y Análisis (`analisis/AnalisisDatos.py`)

Si solo se desea replicar los cálculos físicos sin montar el hardware, basta con ejecutar este script directamente sobre los archivos CSV ubicados en la carpeta `datos/`.

## Requisitos y Dependencias

Para ejecutar el código de este repositorio, es necesario tener instaladas las librerías dispuestas en el archivo `requirements.txt`.
