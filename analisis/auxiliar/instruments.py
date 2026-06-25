# -*- coding: utf-8 -*-
"""
Created on Sat Apr 18 19:52:49 2026

@author: lenovo
"""

import json
import numpy as np

class Instrument:
    """Clase base para todos los instrumentos."""
    def calculate_error(self, value, mode, period):
        raise NotImplementedError("Cada instrumento debe implementar su cálculo de error.")

class HP34401A(Instrument):
    def __init__(self, specs_path="analisis/auxiliar/HP34401A.json", T=23):
        with open(specs_path, "r") as f:
            self.specs = json.load(f)
        self.T = T
        self.range_limits = {
            "DC_Voltage": [0.1, 1, 10, 100, 1000],
            "DC_Resistance": [100, 1000, 10000, 100000, 1000000, 10000000, 100000000],
            "DC_Current": [0.01, 0.1, 1, 3]
        }

    def get_range_str(self, val, mode):
        limits = self.range_limits.get(mode)
        for limit in limits:
            if abs(val) <= limit:
                if "Voltage" in mode: unit = "V"
                elif "Resistance" in mode: unit = "Ohm"
                else: unit = "A"
                
                if limit >= 1e6: return f"{int(limit/1e6)}M{unit}"
                elif limit >= 1e3: return f"{int(limit/1e3)}k{unit}"
                elif limit < 1: return f"{int(limit*1000)}m{unit}"
                else: return f"{int(limit)}{unit}"
        return None

    def calculate_error(self, value, mode, period):
        range_str = self.get_range_str(value, mode)
        if not range_str: return 0.0
        
        # Extraer specs del JSON
        read_pct, range_pct = self.specs[mode][range_str][period]
        T_coeff1_pct, T_coeff2_pct = self.specs[mode][range_str]["T"]
        res = self.specs["Resolution"]
        
        # Valor numérico del rango
        range_val = float(''.join(filter(lambda x: x.isdigit() or x=='.', range_str)))
        if "m" in range_str: range_val /= 1000

        # Incertidumbres tipo B (distribución rectangular -> /sqrt(3))
        u_acc = ((read_pct/100)*abs(value) + (range_pct/100)*range_val) / np.sqrt(3)
        u_T = ((T_coeff1_pct/100)*abs(value) + (T_coeff2_pct/100)*range_val) * abs(self.T - 23) / np.sqrt(3)
        u_res = (res * range_val / 2) / np.sqrt(3)
        
        return np.sqrt(u_acc**2 + u_res**2 + u_T**2)
    
class Termocupla:
    """
    Instrumento de medición térmica con incertidumbre dominada por la apreciación.
    """
    def __init__(self, apreciacion=0.1):
        # La apreciación por defecto es 0.1 °C (equivalente a 0.1 K)
        self.apreciacion = apreciacion

    def calculate_error(self, value=None, mode=None, period=None):
        """
        Devuelve la incertidumbre Tipo B.
        Como la interfaz de DigitalData envía (value, mode, period), los aceptamos
        con kwargs por defecto para evitar errores de argumentos, aunque no los usemos.
        """
        # Según la normativa GUM, si la incertidumbre proviene de la apreciación
        # de un display digital, se asume una distribución rectangular.
        # Incertidumbre estándar = apreciación / sqrt(3)
        
        return self.apreciacion / np.sqrt(3)