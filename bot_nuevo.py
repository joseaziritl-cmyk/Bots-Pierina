import os
import re
import telebot
import gspread
from flask import Flask
from threading import Thread
# Usamos la librería moderna de Google para evitar errores de firma JWT
from google.oauth2.service_account import Credentials

# ==========================================
# 1. CONFIGURACIÓN DE VARIABLES DE ENTORNO
# ==========================================
# Render buscará automáticamente el TOKEN que configuraste en su panel.
TOKEN = os.environ.get("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Nombre EXACTO de tu archivo de Google Sheets
DOCUMENTO_GOOGLE_SHEETS = "DATOS PACIENTES"

# Archivo de credenciales de Google (Debe estar subido en tu GitHub)
CREDENTIALS_FILE = "credenciales.json"

# Columnas ordenadas de la hoja de cálculo
COLUMNAS_EXCEL = [
    "CASO", "CONTACTO", "ACUDIENTE", "NOMBRE DEL PACIENTE", 
    "EDAD", "DIFICULTAD", "DIRECCIÓN", "TIPO DE ATENCIÓN", "DOCTOR/DOCTORA"
]

# ==========================================
# 2. SISTEMA KEEP-ALIVE (SERVIDOR WEB FLASK)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "¡Bot de Pacientes en línea y funcionando!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ==========================================
# 3. LÓGICA PRINCIPAL DEL BOT
# ==========================================
def conectar_google_sheets():
    """Establece conexión usando la librería moderna con tolerancia a desfases de hora."""
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Cargamos las credenciales de forma limpia sin duplicar parámetros
    creds = Credentials.from_service_account_file(
        CREDENTIALS_FILE, 
        scopes=scope
    )
    
    # Aquí aplicamos la tolerancia para el desfase de hora de Render
    # Le damos un margen de 60 segundos (1 minuto) para ir super sobrados
    creds._clock_skew = 60  
        
    client = gspread.authorize(creds)
    sheet = client.open(DOCUMENTO_GOOGLE_SHEETS).sheet1
    return sheet

def extraer_datos_mensaje_flexible(texto_plano):
    """Extrae la información buscando palabras clave sin importar negritas ni mayúsculas."""
    datos_extraidos = {col: "" for col in COLUMNAS_EXCEL}
    
    # Dividimos el mensaje línea por línea
    lineas = texto_plano.split('\n')
    
    for linea in lineas:
        linea_limpia = linea.replace('*', '').replace('<b>', '').replace('</b>', '').replace('<strong>', '').replace('</strong>', '')
        
        if ":" in linea_limpia:
            partes = linea_limpia.split(':', 1)
            titulo = partes[0].strip().lower()
            valor = partes[1].strip()
            
            if "contacto" in titulo:
                datos_extraidos["CONTACTO"] = valor
            elif "acudiente" in titulo:
                datos_extraidos["ACUDIENTE"] = valor
            elif "paciente" in titulo or "nombre" in titulo:
                datos_extraidos["NOMBRE DEL PACIENTE"] = valor
            elif "edad" in titulo:
                datos_extraidos["EDAD"] = valor
            elif "dificultad" in titulo:
                datos_extraidos["DIFICULTAD"] = valor
            elif "direccion" in titulo or "dirección" in titulo:
                datos_extraidos["DIRECCIÓN"] = valor
            elif "atencion" in titulo or "atención" in titulo:
                datos_extraidos["TIPO DE ATENCIÓN"] = valor
            elif "doctor" in titulo or "doctora" in titulo:
                datos_extraidos["DOCTOR/DOCTORA"] = valor
                
    return datos_extraidos

@bot.message_handler(func=lambda message: True)
def registrar_paciente(message):
    texto = message.text if message.text else ""
    
    try:
        datos = extraer_datos_mensaje_flexible(texto)
    except Exception as e:
        bot.reply_to(message, "⚠️ Hubo un problema al procesar las líneas del texto.")
        return

    if not datos["NOMBRE DEL PACIENTE"]:
        bot.reply_to(message, "⚠️ No encontré el nombre del paciente. Asegúrate de incluir una línea que diga 'Paciente: Nombre'.")
        return
    
    try:
        hoja = conectar_google_sheets()
        
        # === LÓGICA DEL AUTO-INCREMENTAL DESDE 17 ===
        total_filas = len(hoja.get_all_values())
        
        if total_filas <= 1:
            numero_caso = 17
        else:
            numero_caso = total_filas + 15
            
        datos["CASO"] = numero_caso
        
        # Preparamos la fila armada con el orden de COLUMNAS_EXCEL
        nueva_fila = [datos[col] for col in COLUMNAS_EXCEL]
        hoja.append_row(nueva_fila)
        
        bot.reply_to(message, f"☁️ ✅ ¡Listo! El paciente '{datos['NOMBRE DEL PACIENTE']}' fue registrado como el **Caso N° {numero_caso}**.")
        print(f"-> Fila agregada con éxito para Caso {numero_caso}: {datos['NOMBRE DEL PACIENTE']}", flush=True)
        
    except Exception as error_google:
        error_msg = str(error_google)
        
        if "200" in error_msg:
            bot.reply_to(message, f"☁️ ✅ ¡Listo! El paciente '{datos['NOMBRE DEL PACIENTE']}' se registró perfectamente.")
        else:
            print(f"!!! ERROR REAL DE GOOGLE SHEETS !!!: {error_msg}", flush=True)
            bot.reply_to(message, f"❌ Error de Google Sheets: {error_msg}")

# ==========================================
# 4. ARRANQUE DEL BOT Y SERVIDORES
# ==========================================
if __name__ == "__main__":
    print(">>> INICIANDO SERVIDOR WEB EN SEGUNDO PLANO <<<", flush=True)
    keep_alive()  # Activa Flask en un hilo separado
    
    print(">>> BOT CON AUTO-INCREMENTAL ENCENDIDO <<<", flush=True)
    bot.infinity_polling()
