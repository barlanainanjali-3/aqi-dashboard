import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import PyPDF2
import re
import math
import io

# --- CPCB AQI CALCULATION LOGIC ---
aqi_breakpoints = {
    'PM10': [{'limit': 50, 'aqi': 50}, {'limit': 100, 'aqi': 100}, {'limit': 250, 'aqi': 200}, {'limit': 350, 'aqi': 300}, {'limit': 430, 'aqi': 400}, {'limit': 1000, 'aqi': 500}],
    'PM25': [{'limit': 30, 'aqi': 50}, {'limit': 60, 'aqi': 100}, {'limit': 90, 'aqi': 200}, {'limit': 120, 'aqi': 300}, {'limit': 250, 'aqi': 400}, {'limit': 1000, 'aqi': 500}],
    'NO2':  [{'limit': 40, 'aqi': 50}, {'limit': 80, 'aqi': 100}, {'limit': 180, 'aqi': 200}, {'limit': 280, 'aqi': 300}, {'limit': 400, 'aqi': 400}, {'limit': 1000, 'aqi': 500}],
    'SO2':  [{'limit': 40, 'aqi': 50}, {'limit': 80, 'aqi': 100}, {'limit': 380, 'aqi': 200}, {'limit': 800, 'aqi': 300}, {'limit': 1600, 'aqi': 400}, {'limit': 3000, 'aqi': 500}],
    'CO':   [{'limit': 1.0, 'aqi': 50}, {'limit': 2.0, 'aqi': 100}, {'limit': 10.0, 'aqi': 200}, {'limit': 17.0, 'aqi': 300}, {'limit': 34.0, 'aqi': 400}, {'limit': 100.0, 'aqi': 500}],
    'O3':   [{'limit': 50, 'aqi': 50}, {'limit': 100, 'aqi': 100}, {'limit': 168, 'aqi': 200}, {'limit': 208, 'aqi': 300}, {'limit': 748, 'aqi': 400}, {'limit': 2000, 'aqi': 500}],
    'NH3':  [{'limit': 200, 'aqi': 50}, {'limit': 400, 'aqi': 100}, {'limit': 800, 'aqi': 200}, {'limit': 1200, 'aqi': 300}, {'limit': 1800, 'aqi': 400}, {'limit': 3000, 'aqi': 500}]
}

def calculate_sub_index(val, param):
    if val is None or math.isnan(val): return 0
    bps = aqi_breakpoints.get(param, [])
    cLo = 0
    iLo = 0
    for bp in bps:
        if val <= bp['limit']:
            return round(((bp['aqi'] - iLo) / (bp['limit'] - cLo)) * (val - cLo) + iLo)
        cLo = bp['limit']
        iLo = bp['aqi']

    # Extrapolate if values exceed boundaries
    if len(bps) >= 2:
        last_bp = bps[-1]
        second_last = bps[-2]
        return round(((last_bp['aqi'] - second_last['aqi']) / (last_bp['limit'] - second_last['limit'])) * (val - second_last['limit']) + second_last['aqi'])
    return 0

def calculate_aqi_for_record(record):
    max_aqi = 0
    for param in ['PM10', 'PM25', 'NO2', 'SO2', 'CO', 'O3', 'NH3']:
        sub_index = calculate_sub_index(record.get(param, 0), param)
        if sub_index > max_aqi:
            max_aqi = sub_index
    return max_aqi

# --- DEMO DATA ---
raw_initial_data = {
     "East Side of Plant (STP - II)": [
    {"hour": 0, "CO": 1.02, "NO2": 17.6, "SO2": 8.8, "PM10": 6, "PM25": 9, "O3": 28.6, "NH3": 5.7},
    {"hour": 1, "CO": 1.04, "NO2": 17.9, "SO2": 8.8, "PM10": 12, "PM25": 7, "O3": 27.9, "NH3": 6.0},
    {"hour": 2, "CO": 1.09, "NO2": 19.5, "SO2": 8.8, "PM10": 10, "PM25": 8, "O3": 24.1, "NH3": 7.2},
    {"hour": 3, "CO": 1.14, "NO2": 20.2, "SO2": 8.8, "PM10": 8, "PM25": 9, "O3": 18.3, "NH3": 8.1},
    {"hour": 4, "CO": 1.20, "NO2": 22.1, "SO2": 8.9, "PM10": 8, "PM25": 9, "O3": 13.7, "NH3": 9.7},
    {"hour": 5, "CO": 1.22, "NO2": 21.9, "SO2": 8.9, "PM10": 8, "PM25": 11, "O3": 11.8, "NH3": 10.2},
    {"hour": 6, "CO": 1.27, "NO2": 22.7, "SO2": 8.9, "PM10": 10, "PM25": 13, "O3": 11.9, "NH3": 12.4},
    {"hour": 7, "CO": 1.50, "NO2": 24.5, "SO2": 9.0, "PM10": 11, "PM25": 15, "O3": 20.6, "NH3": 12.0},
    {"hour": 8, "CO": 1.29, "NO2": 21.3, "SO2": 9.0, "PM10": 35, "PM25": 32, "O3": 35.2, "NH3": 8.2},
    {"hour": 9, "CO": 1.15, "NO2": 20.7, "SO2": 9.2, "PM10": 53, "PM25": 43, "O3": 52.0, "NH3": 7.8},
    {"hour": 10, "CO": 1.00, "NO2": 20.9, "SO2": 9.2, "PM10": 51, "PM25": 40, "O3": 58.3, "NH3": 7.8},
    {"hour": 11, "CO": 0.92, "NO2": 16.5, "SO2": 8.7, "PM10": 44, "PM25": 33, "O3": 63.6, "NH3": 4.3},
    {"hour": 12, "CO": 0.91, "NO2": 14.9, "SO2": 9.3, "PM10": 35, "PM25": 25, "O3": 69.3, "NH3": 3.2},
    {"hour": 13, "CO": 0.90, "NO2": 13.5, "SO2": 8.9, "PM10": 25, "PM25": 21, "O3": 70.0, "NH3": 2.2},
    {"hour": 14, "CO": 0.92, "NO2": 14.5, "SO2": 9.2, "PM10": 21, "PM25": 16, "O3": 73.9, "NH3": 2.9},
    {"hour": 15, "CO": 0.92, "NO2": 14.6, "SO2": 8.9, "PM10": 20, "PM25": 16, "O3": 69.7, "NH3": 3.0},
    {"hour": 16, "CO": 1.06, "NO2": 15.9, "SO2": 9.1, "PM10": 24, "PM25": 16, "O3": 68.3, "NH3": 3.8},
    {"hour": 17, "CO": 1.27, "NO2": 17.3, "SO2": 9.3, "PM10": 36, "PM25": 19, "O3": 65.0, "NH3": 5.0},
    {"hour": 18, "CO": 1.11, "NO2": 19.2, "SO2": 9.0, "PM10": 35, "PM25": 38, "O3": 50.5, "NH3": 6.2},
    {"hour": 19, "CO": 1.13, "NO2": 19.6, "SO2": 8.7, "PM10": 37, "PM25": 56, "O3": 40.5, "NH3": 6.8},
    {"hour": 20, "CO": 1.17, "NO2": 18.3, "SO2": 8.7, "PM10": 41, "PM25": 44, "O3": 38.7, "NH3": 6.2},
    {"hour": 21, "CO": 1.16, "NO2": 22.0, "SO2": 8.6, "PM10": 56, "PM25": 37, "O3": 30.5, "NH3": 9.0},
    {"hour": 22, "CO": 1.13, "NO2": 21.9, "SO2": 8.6, "PM10": 47, "PM25": 33, "O3": 29.5, "NH3": 8.9},
    {"hour": 23, "CO": 1.10, "NO2": 18.6, "SO2": 8.7, "PM10": 40, "PM25": 33, "O3": 34.8, "NH3": 6.7}
  ],
  "West Side of Plant (STP - II)": [
    {"hour": 0, "CO": 0.8, "NO2": 38.3, "SO2": 25.8, "PM10": 52, "PM25": 33, "O3": 11.7, "NH3": 15.0},
    {"hour": 1, "CO": 1.3, "NO2": 33.2, "SO2": 27.2, "PM10": 53, "PM25": 35, "O3": 23.8, "NH3": 13.3},
    {"hour": 2, "CO": 1.2, "NO2": 28.0, "SO2": 28.7, "PM10": 55, "PM25": 36, "O3": 35.8, "NH3": 12.7},
    {"hour": 3, "CO": 1.0, "NO2": 27.7, "SO2": 26.4, "PM10": 55, "PM25": 37, "O3": 13.1, "NH3": 14.5},
    {"hour": 4, "CO": 0.7, "NO2": 29.8, "SO2": 27.7, "PM10": 57, "PM25": 37, "O3": 18.1, "NH3": 14.9},
    {"hour": 5, "CO": 0.4, "NO2": 29.7, "SO2": 26.4, "PM10": 63, "PM25": 42, "O3": 6.4, "NH3": 17.6},
    {"hour": 6, "CO": 0, "NO2": 30.9, "SO2": 28.7, "PM10": 85, "PM25": 56, "O3": 9.5, "NH3": 20.4},
    {"hour": 7, "CO": 0.1, "NO2": 41.7, "SO2": 45.0, "PM10": 109, "PM25": 71, "O3": 29.5, "NH3": 19.5},
    {"hour": 8, "CO": 0.5, "NO2": 38.9, "SO2": 66.1, "PM10": 130, "PM25": 84, "O3": 65.5, "NH3": 17.6},
    {"hour": 9, "CO": 1.1, "NO2": 37.0, "SO2": 110.8, "PM10": 131, "PM25": 86, "O3": 88.2, "NH3": 13.9},
    {"hour": 10, "CO": 1.5, "NO2": 33.6, "SO2": 92.0, "PM10": 105, "PM25": 70, "O3": 108.5, "NH3": 10.6},
    {"hour": 11, "CO": 1.6, "NO2": 17.7, "SO2": 37.9, "PM10": 73, "PM25": 48, "O3": 127.8, "NH3": 8.5},
    {"hour": 12, "CO": 1.6, "NO2": 12.3, "SO2": 32.5, "PM10": 48, "PM25": 32, "O3": 132.5, "NH3": 7.5},
    {"hour": 13, "CO": 1.6, "NO2": 12.7, "SO2": 31.3, "PM10": 34, "PM25": 22, "O3": 135.6, "NH3": 7.5},
    {"hour": 14, "CO": 1.6, "NO2": 15.7, "SO2": 35.5, "PM10": 27, "PM25": 18, "O3": 136.9, "NH3": 7.6},
    {"hour": 15, "CO": 1.6, "NO2": 14.2, "SO2": 31.6, "PM10": 24, "PM25": 16, "O3": 133.9, "NH3": 7.1},
    {"hour": 16, "CO": 1.6, "NO2": 13.6, "SO2": 26.6, "PM10": 23, "PM25": 18, "O3": 138.2, "NH3": 7.3},
    {"hour": 17, "CO": 1.4, "NO2": 18.3, "SO2": 23.5, "PM10": 25, "PM25": 22, "O3": 134.8, "NH3": 8.4},
    {"hour": 18, "CO": 1.2, "NO2": 24.1, "SO2": 25.8, "PM10": 31, "PM25": 28, "O3": 111.0, "NH3": 10.3},
    {"hour": 19, "CO": 0.9, "NO2": 30.4, "SO2": 28.6, "PM10": 39, "PM25": 31, "O3": 93.9, "NH3": 12.3},
    {"hour": 20, "CO": 0.7, "NO2": 38.7, "SO2": 55.8, "PM10": 45, "PM25": 33, "O3": 82.1, "NH3": 12.5},
    {"hour": 21, "CO": 0.8, "NO2": 40.0, "SO2": 72.0, "PM10": 52, "PM25": 35, "O3": 74.4, "NH3": 12.5},
    {"hour": 22, "CO": 0.7, "NO2": 30.3, "SO2": 62.4, "PM10": 58, "PM25": 37, "O3": 78.0, "NH3": 11.9},
    {"hour": 23, "CO": 1.0, "NO2": 25.6, "SO2": 52.2, "PM10": 59, "PM25": 37, "O3": 85.1, "NH3": 11.9}
  ],
  "North Side (E&F Colony)": [
    {"hour": 0, "CO": 1.1, "NO2": 40.5, "SO2": 18.2, "PM10": 44, "PM25": 29, "O3": 10.9, "NH3": 2.8},
    {"hour": 1, "CO": 1.1, "NO2": 36.4, "SO2": 17.8, "PM10": 26, "PM25": 32, "O3": 12.4, "NH3": 3.1},
    {"hour": 2, "CO": 1.0, "NO2": 36.1, "SO2": 18.1, "PM10": 37, "PM25": 30, "O3": 12.0, "NH3": 3.1},
    {"hour": 3, "CO": 1.0, "NO2": 36.0, "SO2": 18.1, "PM10": 45, "PM25": 32, "O3": 11.6, "NH3": 3.1},
    {"hour": 4, "CO": 1.2, "NO2": 43.7, "SO2": 18.0, "PM10": 49, "PM25": 34, "O3": 9.8, "NH3": 2.7},
    {"hour": 5, "CO": 1.2, "NO2": 56.4, "SO2": 17.6, "PM10": 54, "PM25": 38, "O3": 6.8, "NH3": 2.1},
    {"hour": 6, "CO": 1.3, "NO2": 56.7, "SO2": 18.1, "PM10": 68, "PM25": 47, "O3": 6.4, "NH3": 2.1},
    {"hour": 7, "CO": 1.4, "NO2": 56.4, "SO2": 18.4, "PM10": 89, "PM25": 57, "O3": 10.8, "NH3": 2.5},
    {"hour": 8, "CO": 1.4, "NO2": 53.4, "SO2": 19.0, "PM10": 107, "PM25": 74, "O3": 18.3, "NH3": 3.3},
    {"hour": 9, "CO": 1.2, "NO2": 46.6, "SO2": 18.9, "PM10": 128, "PM25": 93, "O3": 24.0, "NH3": 3.5},
    {"hour": 10, "CO": 1.1, "NO2": 50.0, "SO2": 19.2, "PM10": 127, "PM25": 96, "O3": 25.7, "NH3": 3.2},
    {"hour": 11, "CO": 1.0, "NO2": 38.9, "SO2": 20.0, "PM10": 105, "PM25": 78, "O3": 28.4, "NH3": 3.6},
    {"hour": 12, "CO": 1.0, "NO2": 27.7, "SO2": 19.8, "PM10": 79, "PM25": 59, "O3": 32.7, "NH3": 4.1},
    {"hour": 13, "CO": 0.9, "NO2": 26.2, "SO2": 19.1, "PM10": 64, "PM25": 48, "O3": 33.9, "NH3": 4.2},
    {"hour": 14, "CO": 0.9, "NO2": 27.6, "SO2": 19.1, "PM10": 50, "PM25": 38, "O3": 35.6, "NH3": 4.3},
    {"hour": 15, "CO": 0.9, "NO2": 25.3, "SO2": 18.7, "PM10": 42, "PM25": 32, "O3": 34.7, "NH3": 4.5},
    {"hour": 16, "CO": 0.9, "NO2": 25.7, "SO2": 18.5, "PM10": 33, "PM25": 33, "O3": 35.2, "NH3": 4.6},
    {"hour": 17, "CO": 0.9, "NO2": 25.7, "SO2": 18.7, "PM10": 36, "PM25": 32, "O3": 37.0, "NH3": 4.4},
    {"hour": 18, "CO": 0.9, "NO2": 31.9, "SO2": 18.3, "PM10": 43, "PM25": 30, "O3": 32.1, "NH3": 3.8},
    {"hour": 19, "CO": 1.1, "NO2": 41.8, "SO2": 18.1, "PM10": 52, "PM25": 39, "O3": 24.9, "NH3": 3.5},
    {"hour": 20, "CO": 1.2, "NO2": 41.2, "SO2": 18.4, "PM10": 61, "PM25": 59, "O3": 23.0, "NH3": 3.9},
    {"hour": 21, "CO": 1.2, "NO2": 63.3, "SO2": 18.5, "PM10": 74, "PM25": 59, "O3": 16.5, "NH3": 2.4},
    {"hour": 22, "CO": 1.1, "NO2": 45.4, "SO2": 18.4, "PM10": 83, "PM25": 61, "O3": 19.9, "NH3": 3.5},
    {"hour": 23, "CO": 1.1, "NO2": 36.5, "SO2": 17.8, "PM10": 81, "PM25": 57, "O3": 22.4, "NH3": 3.7}
  ],
  "South Side (Shramik Vihar Colony)": [
    {"hour": 0, "CO": 1.78, "NO2": 66.4, "SO2": 19.0, "PM10": 33.5, "PM25": 69, "O3": 0.7, "NH3": 4.7},
    {"hour": 1, "CO": 1.93, "NO2": 47.7, "SO2": 18.9, "PM10": 31, "PM25": 66, "O3": 0.8, "NH3": 4.9},
    {"hour": 2, "CO": 1.99, "NO2": 59.0, "SO2": 17.8, "PM10": 29.6, "PM25": 55, "O3": 0.5, "NH3": 4.0},
    {"hour": 3, "CO": 1.90, "NO2": 93.1, "SO2": 17.9, "PM10": 32, "PM25": 57, "O3": 0.2, "NH3": 1.4},
    {"hour": 4, "CO": 1.95, "NO2": 95.3, "SO2": 17.9, "PM10": 34, "PM25": 67, "O3": 0.2, "NH3": 1.4},
    {"hour": 5, "CO": 2.04, "NO2": 82.3, "SO2": 17.9, "PM10": 37.9, "PM25": 10, "O3": 0.3, "NH3": 1.5},
    {"hour": 6, "CO": 2.16, "NO2": 95.3, "SO2": 18.3, "PM10": 37.4, "PM25": 10, "O3": 0.3, "NH3": 1.9},
    {"hour": 7, "CO": 2.15, "NO2": 80.1, "SO2": 19.3, "PM10": 39.7, "PM25": 11, "O3": 7.7, "NH3": 4.9},
    {"hour": 8, "CO": 1.87, "NO2": 52.2, "SO2": 27.4, "PM10": 70.2, "PM25": 36, "O3": 24.2, "NH3": 5.2},
    {"hour": 9, "CO": 1.71, "NO2": 40.5, "SO2": 44.6, "PM10": 88.9, "PM25": 51, "O3": 43.1, "NH3": 5.2},
    {"hour": 10, "CO": 1.47, "NO2": 35.6, "SO2": 36.9, "PM10": 85.3, "PM25": 41, "O3": 51.9, "NH3": 5.1},
    {"hour": 11, "CO": 1.39, "NO2": 19.9, "SO2": 25.3, "PM10": 66.3, "PM25": 23, "O3": 65.8, "NH3": 4.8},
    {"hour": 12, "CO": 1.33, "NO2": 13.0, "SO2": 24.1, "PM10": 49.9, "PM25": 66, "O3": 73.2, "NH3": 4.7},
    {"hour": 13, "CO": 1.28, "NO2": 12.4, "SO2": 23.1, "PM10": 42.9, "PM25": 40, "O3": 76.4, "NH3": 4.7},
    {"hour": 14, "CO": 1.30, "NO2": 15.2, "SO2": 26.3, "PM10": 27.6, "PM25": 35, "O3": 77.8, "NH3": 4.7},
    {"hour": 15, "CO": 1.27, "NO2": 15.9, "SO2": 26.7, "PM10": 20.7, "PM25": 30, "O3": 77.6, "NH3": 4.8},
    {"hour": 16, "CO": 1.27, "NO2": 15.1, "SO2": 23.8, "PM10": 23.2, "PM25": 25, "O3": 81.3, "NH3": 4.7},
    {"hour": 17, "CO": 1.32, "NO2": 13.3, "SO2": 20.8, "PM10": 30.1, "PM25": 20, "O3": 82.8, "NH3": 4.7},
    {"hour": 18, "CO": 1.46, "NO2": 21.5, "SO2": 19.4, "PM10": 40.4, "PM25": 15, "O3": 44.1, "NH3": 4.9},
    {"hour": 19, "CO": 1.63, "NO2": 26.1, "SO2": 19.9, "PM10": 56.4, "PM25": 15, "O3": 47.2, "NH3": 5.0},
    {"hour": 20, "CO": 1.63, "NO2": 30.1, "SO2": 20.2, "PM10": 65.4, "PM25": 25, "O3": 41.1, "NH3": 5.4},
    {"hour": 21, "CO": 1.60, "NO2": 32.9, "SO2": 19.5, "PM10": 74.9, "PM25": 32, "O3": 32.4, "NH3": 5.4},
    {"hour": 22, "CO": 1.61, "NO2": 31.6, "SO2": 19.7, "PM10": 72.3, "PM25": 31, "O3": 24.3, "NH3": 5.7},
    {"hour": 23, "CO": 1.65, "NO2": 34.4, "SO2": 18.9, "PM10": 67.8, "PM25": 28, "O3": 13.6, "NH3": 5.6}
  ],
  "Cement Plant": [
    {"hour": 0, "CO": 1.3, "NO2": 34.6, "SO2": 20.7, "PM10": 72, "PM25": 47, "O3": 89.6, "NH3": 6.0},
    {"hour": 1, "CO": 1.3, "NO2": 36.3, "SO2": 22.7, "PM10": 71, "PM25": 43, "O3": 60.6, "NH3": 6.0},
    {"hour": 2, "CO": 1.3, "NO2": 35.1, "SO2": 21.2, "PM10": 71, "PM25": 39, "O3": 73.1, "NH3": 6.0},
    {"hour": 3, "CO": 1.3, "NO2": 36.6, "SO2": 22.7, "PM10": 78, "PM25": 47, "O3": 80.2, "NH3": 6.1},
    {"hour": 4, "CO": 1.3, "NO2": 37.2, "SO2": 18.5, "PM10": 89, "PM25": 54, "O3": 69.5, "NH3": 6.0},
    {"hour": 5, "CO": 1.4, "NO2": 36.6, "SO2": 19.8, "PM10": 99, "PM25": 59, "O3": 9.2, "NH3": 6.1},
    {"hour": 6, "CO": 1.5, "NO2": 36.1, "SO2": 19.4, "PM10": 104, "PM25": 67, "O3": 25.7, "NH3": 6.0},
    {"hour": 7, "CO": 1.8, "NO2": 35.3, "SO2": 20.1, "PM10": 109, "PM25": 67, "O3": 71.5, "NH3": 6.0},
    {"hour": 8, "CO": 1.4, "NO2": 33.4, "SO2": 19.7, "PM10": 104, "PM25": 65, "O3": 64.7, "NH3": 6.1},
    {"hour": 9, "CO": 1.3, "NO2": 33.3, "SO2": 23.5, "PM10": 104, "PM25": 62, "O3": 99.7, "NH3": 6.1},
    {"hour": 10, "CO": 1.1, "NO2": 33.0, "SO2": 21.6, "PM10": 97, "PM25": 56, "O3": 162.5, "NH3": 6.0},
    {"hour": 11, "CO": 1.0, "NO2": 34.2, "SO2": 21.1, "PM10": 81, "PM25": 50, "O3": 154.9, "NH3": 6.0},
    {"hour": 12, "CO": 1.0, "NO2": 32.9, "SO2": 21.2, "PM10": 71, "PM25": 42, "O3": 100.0, "NH3": 6.0},
    {"hour": 13, "CO": 1.0, "NO2": 33.7, "SO2": 22.6, "PM10": 65, "PM25": 34, "O3": 131.3, "NH3": 6.0},
    {"hour": 14, "CO": 0.9, "NO2": 34.7, "SO2": 19.8, "PM10": 61, "PM25": 30, "O3": 132.3, "NH3": 6.0},
    {"hour": 15, "CO": 0.9, "NO2": 34.0, "SO2": 16.8, "PM10": 56, "PM25": 30, "O3": 99.5, "NH3": 6.0},
    {"hour": 16, "CO": 1.0, "NO2": 34.2, "SO2": 22.8, "PM10": 60, "PM25": 34, "O3": 77.8, "NH3": 6.0},
    {"hour": 17, "CO": 1.1, "NO2": 34.5, "SO2": 20.8, "PM10": 60, "PM25": 34, "O3": 117.7, "NH3": 6.1},
    {"hour": 18, "CO": 1.1, "NO2": 35.0, "SO2": 17.5, "PM10": 61, "PM25": 41, "O3": 56.1, "NH3": 6.1},
    {"hour": 19, "CO": 1.2, "NO2": 34.8, "SO2": 17.2, "PM10": 68, "PM25": 42, "O3": 55.1, "NH3": 5.9},
    {"hour": 20, "CO": 1.2, "NO2": 34.4, "SO2": 25.6, "PM10": 73, "PM25": 42, "O3": 122.8, "NH3": 6.2},
    {"hour": 21, "CO": 1.3, "NO2": 34.1, "SO2": 26.8, "PM10": 69, "PM25": 42, "O3": 101.7, "NH3": 6.0},
    {"hour": 22, "CO": 1.3, "NO2": 34.6, "SO2": 25.9, "PM10": 68, "PM25": 44, "O3": 113.2, "NH3": 5.9},
    {"hour": 23, "CO": 1.4, "NO2": 33.8, "SO2": 28.2, "PM10": 74, "PM25": 40, "O3": 20.9, "NH3": 5.0}
  ]
}

def process_data_with_aqi(data):
    result = {}
    for loc, records in data.items():
        processed_records = []
        for rec in records:
            new_rec = rec.copy()
            new_rec['AQI'] = calculate_aqi_for_record(new_rec)
            processed_records.append(new_rec)
        result[loc] = processed_records
    return result

# --- PDF & TEXT PARSING LOGIC ---
def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + " "
    return text

def parse_extracted_text(text):
    location_mappings = [
        {"key": "EAST", "name": "East Side of Plant (STP - II)"},
        {"key": "WEST", "name": "West Side of Plant (STP - II)"},
        {"key": "NORTH", "name": "North Side (E&F Colony)"},
        {"key": "SOUTH", "name": "South Side (Shramik Vihar Colony)"},
        {"key": "CEMENT", "name": "Cement Plant"}
    ]

    parsed_data = {}
    upper_text = text.upper()

    for i, loc in enumerate(location_mappings):
        start_idx = upper_text.find(loc["key"])
        if start_idx == -1:
            continue

        end_idx = len(upper_text)
        for j, next_loc in enumerate(location_mappings):
            if i == j: continue
            next_idx = upper_text.find(next_loc["key"], start_idx + 10)
            if next_idx != -1 and next_idx < end_idx:
                end_idx = next_idx

        section_text = text[start_idx:end_idx]

        # Bulletproofing: Handle missing CSV columns
        section_text = re.sub(r',\s*,', ',0,', section_text)
        section_text = re.sub(r'["[\]{}]', ' ', section_text)

        # Split by Date
        splits = re.split(r'\d{4}\s*-\s*\d{2}\s*-\s*\d{2}', section_text)
        loc_data = []

        for k in range(1, len(splits)):
            row_text = splits[k]
            numbers = re.findall(r'-?\d+\.?\d*', row_text)

            if numbers and len(numbers) >= 7:
                try:
                    hour_float = float(numbers[0])
                    hour = int(hour_float)

                    if 0 <= hour <= 23 and hour_float == hour:
                        co = float(numbers[1]) if len(numbers) > 1 else 0.0
                        no2 = float(numbers[2]) if len(numbers) > 2 else 0.0
                        so2 = float(numbers[3]) if len(numbers) > 3 else 0.0
                        pm10 = float(numbers[4]) if len(numbers) > 4 else 0.0

                        if len(numbers) == 7:
                            pm25 = 0.0
                            o3 = float(numbers[5])
                            nh3 = float(numbers[6])
                        else:
                            pm25 = float(numbers[5]) if len(numbers) > 5 else 0.0
                            o3 = float(numbers[6]) if len(numbers) > 6 else 0.0
                            nh3 = float(numbers[7]) if len(numbers) > 7 else 0.0

                        record = {
                            "hour": hour, "CO": co, "NO2": no2, "SO2": so2,
                            "PM10": pm10, "PM25": pm25, "O3": o3, "NH3": nh3
                        }
                        record["AQI"] = calculate_aqi_for_record(record)
                        loc_data.append(record)
                except ValueError:
                    continue

        if loc_data:
            # Filter duplicates by hour keeping the first one
            seen = set()
            unique_data = []
            loc_data.sort(key=lambda x: x['hour'])
            for rec in loc_data:
                if rec['hour'] not in seen:
                    unique_data.append(rec)
                    seen.add(rec['hour'])
            parsed_data[loc["name"]] = unique_data

    return parsed_data if parsed_data else None

# --- STREAMLIT UI ---
st.set_page_config(page_title="Automated AQI Dashboard", page_icon="📊", layout="wide")

COLORS = {
    "AQI": "#DC2626", "CO": "#000000", "NO2": "#800080",
    "SO2": "#FFA500", "PM10": "#A52A2A", "PM25": "#059669",
    "O3": "#0000FF", "NH3": "#008080"
}
PARAMETERS = ["AQI", "CO", "NO2", "SO2", "PM10", "PM25", "O3", "NH3"]

if 'aqi_data' not in st.session_state:
    st.session_state.aqi_data = process_data_with_aqi(raw_initial_data)

st.title("📊 Automated AQI Dashboard")
st.caption("Jindal Steel Limited, Raigarh C.G.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("☁️ Data Input")
    st.info("Upload your daily PDF report. If the PDF fails, you can copy the raw text and paste it below.")

    uploaded_file = st.file_uploader("Upload PDF File", type=["pdf"])
    if uploaded_file is not None:
        try:
            text = extract_text_from_pdf(uploaded_file)
            parsed_data = parse_extracted_text(text)
            if parsed_data:
                st.session_state.aqi_data = parsed_data
                st.success(f"Successfully processed {uploaded_file.name}")
            else:
                st.error("Could not extract valid data. Ensure it contains dates (YYYY-MM-DD) followed by hourly metrics.")
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")

    st.markdown("---")
    pasted_text = st.text_area("Or paste the raw text here...", height=150)
    if st.button("Process Pasted Text"):
        if pasted_text.strip():
            parsed_data = parse_extracted_text(pasted_text)
            if parsed_data:
                st.session_state.aqi_data = parsed_data
                st.success("Successfully processed pasted text!")
            else:
                st.error("Could not extract valid data.")

# --- MAIN CONTENT ---
if st.session_state.aqi_data:
    locations = list(st.session_state.aqi_data.keys())

    # Location tabs
    tabs = st.tabs(locations)

    for i, loc in enumerate(locations):
        with tabs[i]:
            st.subheader(f"📄 {loc}")

            # Prepare DataFrame for Plotly
            df = pd.DataFrame(st.session_state.aqi_data[loc])

            fig = go.Figure()

            for param in PARAMETERS:
                # Add text labels only to AQI
                mode = 'lines+markers+text' if param == 'AQI' else 'lines+markers'
                text_vals = df['AQI'] if param == 'AQI' else None

                fig.add_trace(go.Scatter(
                    x=df['hour'],
                    y=df[param],
                    name=param,
                    mode=mode,
                    text=text_vals,
                    textposition="top center",
                    textfont=dict(color=COLORS[param], size=11, family="Arial Black" if param == 'AQI' else "Arial"),
                    line=dict(color=COLORS[param], width=3 if param == 'AQI' else 2),
                    marker=dict(size=8 if param == 'AQI' else 5)
                ))

            # Add CPCB Exceedance Line
            fig.add_hline(
                y=100,
                line_dash="dash",
                line_color="#EF4444",
                annotation_text="AQI Exceedance Limit (100)",
                annotation_position="top left",
                annotation_font_color="#EF4444",
                annotation_font_size=13
            )

            fig.update_layout(
                xaxis=dict(
                    title="Hour of Day",
                    tickmode='linear',
                    tick0=0,
                    dtick=1,
                    tickformat="d",
                    tickvals=list(range(24)),
                    ticktext=[f"{h}:00" for h in range(24)]
                ),
                yaxis=dict(title="Concentration & AQI"),
                hovermode="x unified",
                height=500,
                margin=dict(l=20, r=20, t=30, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )

            # Display chart
            st.plotly_chart(fig, use_container_width=True)

            st.info("💡 **Understanding the Chart:** The bold red line calculates the overall **Air Quality Index (AQI)** based on CPCB standards. The dashed horizontal line at **100** represents the exceedance limit for satisfactory air quality. **To download this graph:** Hover over the top right corner of the chart and click the camera icon (📷 'Download plot as a png').")
else:
    st.warning("No data available. Please upload a PDF or paste data in the sidebar.")
