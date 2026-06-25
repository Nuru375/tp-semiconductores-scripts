# -*- coding: utf-8 -*-
"""
Created on Wed May 13 14:51:15 2026
@author: Agustin O. Umedez
Various tools for general work
"""

import os
import re

def generar_proximo_nombre(directorio, descripcion="", prefijo="mediciones_", extension=".csv"):
    """
    Busca el número n más alto en archivos 'mediciones_n_*.csv' o 'mediciones_n.csv'
    y devuelve el nombre para el archivo 'n+1' con la nueva descripción.
    """
    # 1. Creamos la carpeta si no existe para evitar errores [cite: 1311]
    if not os.path.exists(directorio):
        os.makedirs(directorio)
        desc_str = f"_{descripcion}" if descripcion else ""
        return os.path.join(directorio, f"{prefijo}1{desc_str}{extension}")

    # 2. Listamos los archivos de la carpeta
    archivos = os.listdir(directorio)
    
    # 3. El nuevo patrón: prefijo + número + (opcionalmente un guion bajo y más texto) + extensión
    # (\d+) captura el número. (?:_.*)? es un grupo que no captura pero permite texto extra.
    patron = re.compile(rf"^{prefijo}(\d+)(?:_.*)?\{extension}$")
    
    numeros_encontrados = []
    for nombre in archivos:
        coincidencia = patron.match(nombre)
        if coincidencia:
            # Extraemos el número capturado en el primer grupo
            numeros_encontrados.append(int(coincidencia.group(1)))
    
    # 4. Determinamos el siguiente número usando el máximo encontrado 
    siguiente_n = max(numeros_encontrados, default=0) + 1
    
    # 5. Construimos el nuevo nombre
    desc_str = f"_{descripcion}" if descripcion else ""
    nuevo_nombre = f"{prefijo}{siguiente_n}{desc_str}{extension}"
    
    return os.path.join(directorio, nuevo_nombre)

# --- Ejemplo de uso en tu script de adquisición ---
# nombre_archivo = generar_proximo_nombre("DATA_TP2", descripcion="difusorprolijo_50mA")
# print(f"El archivo se guardará como: {nombre_archivo}")


def ultimo_archivo(directorio, prefijo="mediciones_", extension=".csv"):
    """
    Busca el último archivo del directorio que tengan la forma 'mediciones_n.csv' o
    'mediciones_n_*.csv' y devuelve el nombre completo de dicho archivo.
    """
    
    # Listamos los archivos de la carpeta
    archivos = os.listdir(directorio)
    
    # El nuevo patrón: prefijo + número + (opcionalmente un guion bajo y más texto) + extensión
    # (\d+) captura el número. (?:_.*)? es un grupo que no captura pero permite texto extra.
    patron = re.compile(rf"^{prefijo}(\d+)(?:_.*)?\{extension}$")
    
    lista_tuplas = []
    for nombre in archivos:
        if (coincidencia := patron.match(nombre)):
            # Extraemos el número capturado en el primer grupo y su índice
            lista_tuplas.append(
                (int(coincidencia.group(1)), nombre)
            )
    
    # Determinamos el último número usando el máximo encontrado 
    ultimo_archivo = max(lista_tuplas, key=lambda x: x[0])[1]
    
    return os.path.join(directorio, ultimo_archivo)

