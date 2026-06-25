import matplotlib.pyplot as plt
import cv2
import subprocess
import pandas as pd
import numpy as np
from uncertainties import unumpy as unp
import time
from string import Template
from analysis import DigitalData
from auxiliar.instruments import HP34401A, Termocupla

def get_df(a, b, root: str, archivo: Template, skip=[]):
    df_list = []
    for n in range(a, b+1):
        if n in skip: continue # Archivos feos, skip
        df_list.append( pd.read_csv(root + archivo.substitute(numero=n)) )
    df = pd.concat(df_list, axis=0, ignore_index=True)
    return df

def fix_df(df1, op):
    """
    op = 0:  Enfriamiento
    op = 1:  Calentamiento
    """
    df1["Temperatura (C)"] = df1["Temperatura (K)"] - 273.15
    
    # Fila donde llegó a su mínimo
    indice_cero = df1['Temperatura (C)'].idxmin()
    if op:
        df1.loc[:indice_cero, 'Temperatura_Real (C)'] = df1['Temperatura (C)'] * -1
        df1.loc[indice_cero:, 'Temperatura_Real (C)'] = df1['Temperatura (C)']
    else:
        df1.loc[:indice_cero, 'Temperatura_Real (C)'] = df1['Temperatura (C)']
        df1.loc[indice_cero:, 'Temperatura_Real (C)'] = df1['Temperatura (C)'] * -1

    df1['Temperatura_Real (K)'] = df1['Temperatura_Real (C)'] + 273.15

    return df1

def get_T_ocr(x, root, archivo: Template):
    def leer_pantalla_lcd(imagen_recortada, nombre_temp="temp_crop.png"):
        """
        Guarda el recorte de OpenCV temporalmente y utiliza ssocr para leerlo.
        """
        alto, ancho = imagen_recortada.shape[:2]
        alpha = 0.1             # Factor de "shear"
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
        
        # Convertimos a escala de grises
        gris = cv2.cvtColor(frame_ampliado, cv2.COLOR_BGR2GRAY)
        
        # Suavizado (Gaussian Blur) - Reducido para no borrar el punto
        blur = cv2.GaussianBlur(gris, (5, 5), 0)

        # Guardar el recorte de OpenCV en el disco para que ssocr pueda leerlo
        cv2.imwrite(nombre_temp, blur)
        
        # Configuración de parámetros de SSOCR
        RUTA_SSOCR = "ssocr"
        comando = [
            "wsl",
            RUTA_SSOCR,
            "-d", "-1",         # Detectar cantidad automática de dígitos
            "-c", "digit",      # Restringir a caracteres numéricos
            "-r", "5",          # Height to Width ratio (H/W) del dígito 1
            "-C",               # Ignorar puntos decimales
            # "-T",               # Usar umbral adaptativo (Iterative Thresholding)
            "-M", "10x80",      # Dimensiones mínimas de un potencial dígito
            "-t", "45",         # Umbral estricto manual (mayor -t, menos estricto)
            "-D",               # Guardar imagen de diagnóstico
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
            # Parche mágico: Reemplazamos la 'p' o 'P' por un '1'
            if ('p' in lectura) or ('P' in lectura):
                lectura = lectura.replace("p", "1").replace("P", "1")
                print("Ojito bob esponja, reemplacé una 'p' por un 1.")
            return int(lectura) / 10
            
        except subprocess.CalledProcessError as e:
            print(f"Error al leer la imagen. Código: {e.returncode}")
            # stderr suele contener pistas sobre si la imagen era muy oscura/clara
            print(f"Detalle: {e.stderr}")
            return None
        except FileNotFoundError:
            print("¡Error! No se encontró el ejecutable de ssocr en el sistema.")
            return None

    T, DT = [], []
    for i in range(x+1):
        T_Celcius, dt_l = [], []
        for j in range(4+1):
            # t = time.perf_counter()
            frame = cv2.imread((root+archivo.substitute(m=i, n=j)))
            if frame is None: break
            if x==17:
                crop = frame[236:290, 300:405] # [y1:y2, x1:x2]
            else: # x=341
                crop = frame[110:165, 135:240] # [y1:y2, x1:x2]
            lectura = leer_pantalla_lcd(crop)
            if lectura is None:
                print("Ojo, lectura = None.")
                continue
            # dt = time.perf_counter() - t
            # dt_l.append(dt)
            T_Celcius.append( lectura )
            # print(f"[{dt:.2g}] T (C) = {lectura}")
            print(f"[T (C) = {lectura}")
        # dt_medio = np.mean(dt_l)
        # DT.append(dt_medio)
        lectura_final = np.mean(T_Celcius)
        T.append( lectura_final )
        # print(f"[{dt_medio:.2g}] T_final (C) = {lectura_final}")
        print(f"T_final (C) = {lectura_final}")
    # return T, np.mean(DT)
    return T

def unificar_dfs(df_crudos_l: list[pd.DataFrame], mapeos, root):
    df_l = []
    for i, df in enumerate(df_crudos_l):
        df_temp = df.copy()
        df_temp = df_temp.rename(columns=mapeos[i])
        df_temp = df_temp[['Resistencia [Ohm]', 'Temperatura_OCR [C]', 'Resistencia_TERMISTOR [Ohm]']]
        df_l.append(df_temp)

    df_final = pd.concat(df_l, ignore_index=True)
    df_final.to_csv(root)
    return df_final

p = (-3.41, 3402)
uA = (0.01, 6)
a, b = p
uA_a, uA_b = uA
temperatura = lambda R: b/(np.log(R) - a)

root = r"datos"

# --- T baja --- #
df1 = get_df(40, 48, root, Template(r"\me_${numero}_enfriamiento_2.csv")) # Enfriamiento
df1 = fix_df(df1, op=0)

df2 = get_df(49, 51, root, Template(r"\me_${numero}_calentamiento_2.csv")) # Calentamiento
df2 = fix_df(df2, op=1)
df2 = df2[df2['Temperatura_Real (K)'] > 74]

# --- T ambiente --- #
df_ambiente = pd.read_csv(root + r"\FINAL_t_ambiente.csv")
df_ambiente["Temperatura_OCR [K]"] = df_ambiente["Temperatura_OCR [C]"] + 273.15
df_ambiente["Temperatura_TERMISTOR [K]"] = temperatura( df_ambiente["Resistencia_TERMISTOR [Ohm]"] )
df_ambiente_1 = df_ambiente.iloc[:147, :] # Medición 1
df_ambiente_2 = df_ambiente.iloc[439:, :] # Medición 2

# --- T alta --- #
# Enfriamiento
df3 = get_df(3, 29, root, Template(r"\me_${numero}_enfriamiento_1.csv"), [7,9,10,12,18,22,23,24,25,26,27,28])
# Calentamiento
df4 = get_df(1, 2, root, Template(r"\me_${numero}_calentamiento_1.csv"))



# --- Plots --- #
## Config común
ms = 2
lw = 2

## Plot 1: T vs R
fig, ax1 = plt.subplots(figsize=(7, 4))

# ax1.plot(df1["Temperatura_Real (K)"], df1["Resistencia (Ohm)"], "--oc", markersize=ms, label="Enfriamiento")
ax1.plot(df2["Temperatura_Real (K)"], df2["Resistencia (Ohm)"], "s", color="firebrick", markersize=ms, label="Calentamiento (1)")
# ax1.plot(df_ambiente_1["Temperatura_OCR [K]"], df_ambiente_1["Resistencia [Ohm]"], "--o", color="green", markersize=ms)
ax1.plot(df_ambiente_2["Temperatura_OCR [K]"], df_ambiente_2["Resistencia [Ohm]"], "s", color="red", markersize=ms, label="Calentamiento (2)")
# ax1.plot(df_ambiente_2["Temperatura_TERMISTOR [K]"], df_ambiente_2["Resistencia [Ohm]"], "s", color="red", markersize=ms, label="Calentamiento (2)")
ax1.plot(df3["Temperatura (K)"], df3["Resistencia (Ohm)"], "s", color="cornflowerblue", markersize=ms, label="Enfriamiento (3)")
# ax1.plot(df4["Temperatura (K)"], df4["Resistencia (Ohm)"], "--or", markersize=3, label="Calentamiento")

ax1.grid()
ax1.legend(loc='upper left')
ax1.set_xlabel("T [K]")
ax1.set_ylabel("R [Ohm]")

ax2 = ax1.secondary_xaxis('top', functions=(lambda x: x-273.15, lambda x: x+273.15))
ax2.set_xlabel("T [C]")

fig.tight_layout()
plt.show()

## Plot 2: ln(T) vs ln(R) --> Región Extrínsica
fig, ax1 = plt.subplots(figsize=(7, 4))

ax1.plot(np.log(df2["Temperatura_Real (K)"]), np.log(df2["Resistencia (Ohm)"]), "s", color="firebrick", markersize=ms, label="Calentamiento (1)")
ax1.plot(np.log(df_ambiente_2["Temperatura_OCR [K]"]), np.log(df_ambiente_2["Resistencia [Ohm]"]), "s", color="red", markersize=ms, label="Calentamiento (2)")
# ax1.plot(df_ambiente_2["Temperatura_TERMISTOR [K]"], np.log(df_ambiente_2["Resistencia [Ohm]"]), "s", color="red", markersize=ms, label="Calentamiento (2)")
ax1.plot(np.log(df3["Temperatura (K)"]), np.log(df3["Resistencia (Ohm)"]), "s", color="cornflowerblue", markersize=ms, label="Enfriamiento (3)")

ax1.grid()
ax1.legend(loc='upper left')
ax1.set_xlabel(r"$\ln{{T}}$")
ax1.set_ylabel(r"$\ln{{R}}$")

ax2 = ax1.secondary_xaxis('top', functions=(lambda x: x-273.15, lambda x: x+273.15))
ax2.set_xlabel(r"$\ln{{T}}$")

fig.tight_layout()
plt.show()

## Plot 3: 1/T vs ln(R) --> Región Intrínsica
fig, ax1 = plt.subplots(figsize=(7, 4))

ax1.plot(1/(df2["Temperatura_Real (K)"]), np.log(df2["Resistencia (Ohm)"]), "s", color="firebrick", markersize=ms, label="Calentamiento (1)")
ax1.plot(1/(df_ambiente_2["Temperatura_OCR [K]"]), np.log(df_ambiente_2["Resistencia [Ohm]"]), "s", color="red", markersize=ms, label="Calentamiento (2)")
# ax1.plot(df_ambiente_2["Temperatura_TERMISTOR [K]"], np.log(df_ambiente_2["Resistencia [Ohm]"]), "s", color="red", markersize=ms, label="Calentamiento (2)")
ax1.plot(1/(df3["Temperatura (K)"]), np.log(df3["Resistencia (Ohm)"]), "s", color="cornflowerblue", markersize=ms, label="Enfriamiento (3)")

ax1.grid()
ax1.legend(loc='upper left')
ax1.set_xlabel(r"1/T")
ax1.set_ylabel(r"$\ln{{R}}$")

ax2 = ax1.secondary_xaxis('top', functions=(lambda x: x-273.15, lambda x: x+273.15))
ax2.set_xlabel(r"1/T")

fig.tight_layout()
plt.show()



# --- Análisis de los datos --- #
full_data = pd.DataFrame({
    "Temperatura [K]": pd.concat([df2["Temperatura_Real (K)"], df_ambiente_2["Temperatura_OCR [K]"], df3["Temperatura (K)"]], ignore_index=True),
    "Resistencia [Ohm]": pd.concat([df2["Resistencia (Ohm)"], df_ambiente_2["Resistencia [Ohm]"], df3["Resistencia (Ohm)"]], ignore_index=True)
})
instrumentos = [Termocupla(), HP34401A()]


## Región Extrínsica: Se espera obtener alfa ~ 1.5
lim_inf, lim_sup = 182, 311
df_extrinsico = full_data[(full_data["Temperatura [K]"] > lim_inf) & (full_data["Temperatura [K]"] < lim_sup)]

# modelo: ln(R) = -alfa * ln(T) + B
transformaciones = [
    lambda x: unp.log(x),
    lambda y: unp.log(y)
]
analisis = DigitalData(
    [df_extrinsico["Temperatura [K]"], df_extrinsico["Resistencia [Ohm]"]],
    instruments=instrumentos,
    modes=[None, "DC_Resistance"],
    transforms=transformaciones
)
M, P = analisis.fast()
m, U_m = M
p, U_p = P
alfa, U_alfa = -m, U_m

plt.figure()
plt.title(fr"T $\in$ [{lim_inf}K, {lim_sup}K]")
plt.plot(np.log(df_extrinsico["Temperatura [K]"]),
         np.log(df_extrinsico["Resistencia [Ohm]"]),
         's', color='black', markersize=ms,
         label="Mediciones")
plt.plot((xs := np.linspace(np.log(lim_inf)-.03, np.log(lim_sup)+.03)),
         np.polyval([m, p], xs),
         '--', color='crimson', linewidth=lw,
         label=fr"Ajuste: y = ({m:.3f}$\pm${U_m:.1g})x + ({p:.3f}$\pm${U_p:.1g})")
plt.legend(loc='upper left')
plt.xlabel(r"$\ln{{T}}$")
plt.ylabel(r"$\ln{{R}}$")
plt.grid()
plt.tight_layout()
# plt.savefig("ajuste_region_extrinseca")
plt.show()

print(f"alfa = {alfa:.3f} +/- {U_alfa:.1g}") # -1.341 +/- 0.001

# lim_inf, lim_sup = 279, 302
# termi = df_ambiente_2[(df_ambiente_2["Temperatura_TERMISTOR [K]"] > lim_inf) & (df_ambiente_2["Temperatura_TERMISTOR [K]"] < lim_sup)]
# p, p_cov = np.polyfit(np.log(termi["Temperatura_TERMISTOR [K]"]), np.log(termi["Resistencia [Ohm]"]), 1, cov=True)
# m, A = p
# uA_m, uA_A = np.sqrt(np.diag(p_cov))
# alfa2 = -m
# u_alfa2 = uA_m # Falta propagar el error del multímetro

# plt.figure()
# plt.title(fr"T $\in$ [{lim_inf}K, {lim_sup}K]")
# plt.plot(np.log(termi["Temperatura_TERMISTOR [K]"]),
#          np.log(termi["Resistencia [Ohm]"]),
#          's', color='black', markersize=ms)
# plt.plot((xs := np.linspace(np.log(lim_inf)-.005, np.log(lim_sup)+.005)),
#          np.polyval(p, xs),
#          '--', color='crimson', linewidth=lw)
# plt.legend(loc='upper left')
# plt.xlabel(r"$\ln{{T}}$")
# plt.ylabel(r"$\ln{{R}}$")
# plt.grid()
# plt.tight_layout()
# # plt.savefig("ajuste_region_extrinseca")
# plt.show()

# print(f"{alfa:.2g} +/- {uA_m:.2g}") # -1.9 +/- 0.01


## Región Intrínseca: Se espera obtener Eg ~ 1 a 2 eV
lim_inf, lim_sup = 470, 520
df_intrinsico = full_data[(full_data["Temperatura [K]"] > lim_inf) & (full_data["Temperatura [K]"] < lim_sup)]

# modelo: ln(R) = Eg / (2*kB) * (1 / T) + A  -->  m = Eg / (2*kB)  -->  Eg = 2*kB*m
transformaciones = [
    lambda x: 1 / x,
    lambda y: unp.log(y)
]
analisis = DigitalData(
    [df_intrinsico["Temperatura [K]"], df_intrinsico["Resistencia [Ohm]"]],
    instruments=instrumentos,
    modes=[None, "DC_Resistance"],
    transforms=transformaciones
)
M, P = analisis.fast()
m, U_m = M
p, U_p = P

kB_joule = 1.380649e-23 # joule/K
kB = kB_joule / 1.602176634e-19 # eV/K

Eg = (2*kB) * m
U_Eg = (2*kB) * U_m

ms=3
plt.figure()
plt.title(fr"T $\in$ [{lim_inf}K, {lim_sup}K]")
plt.plot(1/(df_intrinsico["Temperatura [K]"]),
         np.log(df_intrinsico["Resistencia [Ohm]"]),
         's', color='black', markersize=ms,
         label="Mediciones")
plt.plot((xs := np.linspace(1/(lim_inf)+.000003, 1/(lim_sup)-.000003)),
         np.polyval([m, p], xs),
         '--', color='crimson', linewidth=lw,
         label=fr"Ajuste: y = ({m:.0f}$\pm${U_m:.0f})x + ({p:.2f}$\pm${U_p:.1g})")
plt.legend(loc='upper left')
plt.xlabel(r"1/T")
plt.ylabel(r"$\ln{{R}}$")
plt.grid()
plt.tight_layout()
# plt.savefig("ajuste_region_intrinseca")
plt.show()

print(f"Eg = {Eg:.3f} +/- {U_Eg:.1g}") # 0.558 +/- 0.004 eV


