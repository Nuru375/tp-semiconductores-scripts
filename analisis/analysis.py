# -*- coding: utf-8 -*-
"""
Created on Mon Mar 30 14:49:19 2026
@author: Agustin 0. Umedez
Classes for data treatments
"""

import numpy as np
import scipy.stats as st
from uncertainties import unumpy

class Data:
    def __init__(self, data):
        self.data = np.array(data)
        # mode: 0 [univariado], 1 [bivariado (x, y)]
        self.mode = 0 if len(self.data.shape)==1 else 1

    def mean(self):
        return np.mean(self.data, axis=1) if self.mode else np.mean(self.data)

    def std_mean(self):
        """Error estándar de la media (Tipo A)"""
        n = self.data.shape[1] if self.mode else len(self.data)
        return np.std(self.data, axis=1 if self.mode else 0, ddof=1) / np.sqrt(n)

    def linear_fit(self, values=True, stats=False):
        if not self.mode or len(self.data) < 2:
            raise ValueError("So' un wachin, te falta el eje X o datos suficientes.")
        
        x, y = self.data
        params, cov = np.polyfit(x, y, deg=1, cov=True)
        
        if values:
            xs = np.linspace(x[0], x[-1])
            ys = np.polyval(params, xs)
        
        if stats:
            m, p = params
            sdv_m, sdv_p = np.sqrt(np.diag(cov))
            return ((m, sdv_m), (p, sdv_p)) if not values else ((m, sdv_m), (p, sdv_p), ys)
        return params if not values else (params, ys)

class DigitalData(Data):
    # Añadimos 'transforms' como kwarg (espera lambdas)
    def __init__(self, data, instruments, modes="DC_Voltage", periods="1y", transforms=None):
        super().__init__(data)
        
        # Normalización de parámetros para soportar múltiples instrumentos
        n_axes = 2 if self.mode else 1
        
        self.instruments = self._to_list(instruments, n_axes) # Objetos de la clase HP34401A o similar
        self.modes = self._to_list(modes, n_axes)
        self.periods = self._to_list(periods, n_axes)
        self.transforms = self._to_list(transforms, n_axes) # Lambdas de transformación
        
        # Arrays para guardar las incertidumbres propagadas internamente
        self.propagated_uB = []
        final_data = []
        
        # Guardamos una copia de los datos crudos
        raw_data = np.copy(self.data)
        
        # Procesamos eje por eje (X e Y)
        for axis in range(n_axes):
            axis_raw_data = raw_data[axis] if n_axes == 2 else raw_data
            
            instrument = self.instruments[axis]
            
            # 1. Obtener la incertidumbre cruda
            if instrument is None:
                raw_uB = np.zeros_like(axis_raw_data, dtype=float)
            else:
                # Iteramos sobre los puntos para pedirle el error crudo al instrumento
                raw_uB = np.array([instrument.calculate_error(val, self.modes[axis], self.periods[axis]) for val in axis_raw_data])
            
            # 2. Empaquetar el dato y su error (Tratamiento Alternativa 2)
            u_array = unumpy.uarray(axis_raw_data, raw_uB)
            
            # 3. Aplicar lambda si fue enviada por el usuario para este eje
            transform = self.transforms[axis]
            if transform is not None:
                u_array = transform(u_array)
            
            # 4. Desempaquetar y guardar: Valores corregidos y errores propagados
            final_data.append(unumpy.nominal_values(u_array))
            self.propagated_uB.append(unumpy.std_devs(u_array))
            
        # Sobrescribimos self.data con los valores YA transformados para que
        # linear_fit() y mean() ajusten sobre la matemática que querías
        self.data = np.array(final_data[0] if n_axes == 1 else final_data)

    def _to_list(self, param, n):
        """Auxiliar para convertir parámetros únicos en listas para cada eje."""
        if isinstance(param, (list, tuple)):
            return param
        return [param] * n

    def get_uB(self, value=None, axis=0):
        """Obtiene la incertidumbre Tipo B del instrumento correspondiente al eje."""
        instrument = self.instruments[axis]
        
        # Si no se asignó un instrumento (es None), asumimos error Tipo B nulo
        if instrument is None:
            return 0.0
            
        # Al haber usado unumpy, el error ya está propagado para todo el vector.
        # El parámetro 'value' se ignora pero se mantiene para no romper el método fast().
        # Devolvemos el promedio de esa incertidumbre vectorizada.
        return float(np.mean(self.propagated_uB[axis]))
    
    def fast(self, sigmas=1):
        """Reporte rápido con propagación completa."""
        # Factor de cobertura k (t-Student)
        conf = {
            1: 0.68,
            2: 0.95,
            3: 0.997
        }
        n = self.data.shape[1] if self.mode else len(self.data)
        dof = (n - 2) if self.mode else (n - 1)
        alpha = 1 - conf[sigmas]
        k = st.t.ppf(1 - alpha/2, df=dof)

        if not self.mode:
            # Caso una sola magnitud
            val_mean = self.mean()
            uA = self.std_mean()
            uB = self.get_uB(val_mean, axis=0)
            uC = np.sqrt(uA**2 + uB**2)
            return val_mean, k * uC
        
        else:
            # Caso ajuste lineal (Propagación en la pendiente)
            M, P = self.linear_fit(values=False, stats=True)
            m, sm = M # m: pendiente, sm: error del ajuste (Tipo A)
            p, sp = P # p: ordenada, sp: error del ajuste (Tipo A)
            
            # Error instrumental medio (Tipo B)
            x_mean = np.mean(self.data[0])
            y_mean = np.mean(self.data[1])
            uB_x = self.get_uB(x_mean, axis=0)
            uB_y = self.get_uB(y_mean, axis=1)

            # Propagación simplificada a la pendiente
            # sigma_m^2 = (sm_fit)^2 + (uB_slope)^2
            # Aquí uB_slope se aproxima por la propagación de errores sistemáticos
            uB_m = m * np.sqrt((uB_y/y_mean)**2 + (uB_x/x_mean)**2)
            uB_p = p * np.sqrt((uB_y/y_mean)**2 + (uB_x/x_mean)**2)
            
            uC_m = np.sqrt(sm**2 + uB_m**2)
            uC_p = np.sqrt(sp**2 + uB_p**2)
            
            return (m, k * uC_m), (p, k * uC_p)

