import datetime
import requests
import telebot
import time
import json


class BOT_Ruleta:

    def __init__(self):
        # ─── CONFIGURACIÓN DEL BOT ───────────────────────────────────────────
        self.juego = "Auto Roulette"                         # Nombre del juego para los mensajes
        self.token = "8688088883:AAEZNVgOtHlzPyJjPNGeV_mF7xyrpk1P87A"
        self.chat_id = "-1003653886825"
        self.url_API = "https://api-cs.casino.org/svc-evolution-game-events/api/autoroulette?page=0&size=29&sort=data.settledAt,desc&duration=6"
        # ─────────────────────────────────────────────────────────────────────

        # ─── PARÁMETROS DE ESTRATEGIA ─────────────────────────────────────────
        self.martingalas = 2     # Niveles de protección (Martingalas)
        self.aciertos = 3        # Cantidad de repeticiones necesarias para enviar señal
        # ─────────────────────────────────────────────────────────────────────

        # ─── ESTADÍSTICAS DE LA SESIÓN ────────────────────────────────────────
        self.racha_max = 0       # Mejor racha de victorias
        self.racha_actual = 0    # Racha de victorias en curso
        self.victorias = 0       # Total de aciertos
        self.derrotas = 0        # Total de fallos (luego de las martingalas)
        self.empates = 0         # Total de ceros (protección)
        # ─────────────────────────────────────────────────────────────────────

        # ─── CONTADORES INTERNOS ──────────────────────────────────────────────
        self.cont_col_01 = 0     # Contador para Columna 1
        self.cont_col_02 = 0     # Contador para Columna 2
        self.cont_col_03 = 0     # Contador para Columna 3
        self.columnas_objetivo = 0 # Columnas donde se debe apostar
        # ─────────────────────────────────────────────────────────────────────

        # ─── MAPA DE LA RULETA (COLUMNAS) ────────────────────────────────────
        self.ruleta = {
            "03": [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36],   # Columna 3
            "02": [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],   # Columna 2
            "01": [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],   # Columna 1
        }

        # ─── ESTADO OPERATIVO ────────────────────────────────────────────────
        self.gale_actual = 0         # Nivel de martingala actual
        self.analizar = True         # True = Buscando señal | False = Esperando resultado
        self.proteccion_cero = True  # Sugerir siempre cubrir el cero
        self.eliminar_alerta = False # Control para borrar mensajes temporales
        self.id_msg_alerta = None    # ID del mensaje a borrar
        self.historial_resultados = [] # Últimos 20 resultados para análisis
        self.umbral_seguridad = 4.0  # Bajamos un poco para tener más señales (era 5)
        self.conteo_senales = 0      # Contador para resumen cada 10
        self.historial_visual = []   # Historial visual de resultados
        # ─────────────────────────────────────────────────────────────────────

        self.bot = telebot.TeleBot(
            token=self.token,
            parse_mode="MARKDOWN",
            disable_web_page_preview=True
        )

        # ─── SESIÓN DE RED AVANZADA ──────────────────────────────────────────
        self.sesion = requests.Session()
        self.sesion.headers.update({
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "accept": "*/*",
            "accept-language": "es-ES,es;q=0.9",
            "accept-encoding": "gzip, deflate",
            "origin": "https://www.casino.org",
            "referer": "https://www.casino.org/",
            "sec-ch-ua": '"Google Chrome";v="134", "Not.A/Brand";v="8", "Chromium";v="134"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "priority": "u=1, i"
        })
        # ─────────────────────────────────────────────────────────────────────

        # ─── CONTROL DE TIEMPO ───────────────────────────────────────────────
        self.fecha_hoy = str(datetime.datetime.now().strftime("%d/%m/%Y"))
        self.fecha_control = self.fecha_hoy

    # ─────────────────────────────────────────────────────────────────────────
    # REINICIO DIARIO
    # Verifica si cambió el día para resetear estadísticas y enviar resumen.
    # ─────────────────────────────────────────────────────────────────────────
    def reiniciar(self):
        self.fecha_hoy = str(datetime.datetime.now().strftime("%d/%m/%Y"))
        if self.fecha_hoy != self.fecha_control:
            print("🔄 Reiniciando bot por cambio de fecha...")
            self.fecha_control = self.fecha_hoy

            # Enviar marcador final del día anterior
            self.resultados()

            # Resetear contadores de sesión
            self.victorias = 0
            self.derrotas = 0
            self.empates = 0
            self.racha_max = 0
            self.racha_actual = 0
            self.conteo_senales = 0
            self.historial_visual = []

            time.sleep(5)

            # Notificar inicio de nueva sesión
            self.bot.send_message(
                chat_id=self.chat_id,
                text=(
                    f"🟢 *NUEVA SESIÓN INICIADA*\n"
                    f"📅 Fecha: {self.fecha_hoy}\n"
                    f"🎰 Juego: {self.juego}\n"
                    f"🔄 Estadísticas reiniciadas correctamente."
                )
            )
            return True
        else:
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # MARCADOR / RESULTADOS
    # ─────────────────────────────────────────────────────────────────────────
    def resultados(self):
        # Reiniciar contadores de análisis
        self.cont_col_01 = 0
        self.cont_col_02 = 0
        self.cont_col_03 = 0

        total = self.victorias + self.empates + self.derrotas
        asertividad = (100 / total * (self.victorias + self.empates)) if total != 0 else 0
        
        resumen = "\n".join(self.historial_visual) if self.historial_visual else "Esperando operaciones..."

        self.bot.send_message(
            chat_id=self.chat_id,
            text=(
                f"📊 *RESUMEN DE OPERACIONES (10 ÚLTIMAS)*\n"
                f"─────────────────────\n"
                f"{resumen}\n"
                f"─────────────────────\n"
                f"✅ Ganes: {self.victorias} | 🚫 Fallos: {self.derrotas} | 🟠 Ceros: {self.empates}\n"
                f"🎯 Efectividad: {asertividad:,.2f}%\n"
            )
        )

        # Reiniciar para el siguiente ciclo de 10
        self.victorias = 0
        self.derrotas = 0
        self.empates = 0
        self.conteo_senales = 0
        self.historial_visual = []
        return

    # ─────────────────────────────────────────────────────────────────────────
    # ALERTAS DE TELEGRAM
    # ─────────────────────────────────────────────────────────────────────────
    def alerta_senal(self):
        self.id_msg_alerta = self.bot.send_message(
            self.chat_id,
            text="⚠️ *ANALIZANDO POSIBLE ENTRADA...* ⚠️",
        ).message_id
        self.eliminar_alerta = True
        return

    def alerta_gale(self):
        self.id_msg_alerta = self.bot.send_message(
            self.chat_id,
            text=f"⚠️ *PROTECCIÓN #{self.gale_actual}* — Vamos a la Martingala {self.gale_actual}ª"
        ).message_id
        self.eliminar_alerta = True
        return

    # ─────────────────────────────────────────────────────────────────────────
    # ELIMINAR MENSAJE TEMPORAL
    # ─────────────────────────────────────────────────────────────────────────
    def eliminar(self):
        if self.eliminar_alerta:
            try:
                self.bot.delete_message(chat_id=self.chat_id, message_id=self.id_msg_alerta)
            except Exception:
                pass
            self.eliminar_alerta = False

    # ─────────────────────────────────────────────────────────────────────────
    # ENVIAR SEÑAL DE ENTRADA
    # Se activa cuando se cumple la estrategia. Informa las columnas a cubrir.
    # columnas: 12 → columnas 1 y 2 | 13 → columnas 1 y 3 | 23 → columnas 2 y 3
    # ─────────────────────────────────────────────────────────────────────────
    def enviar_senal(self, columnas):
        self.analizar = False

        if columnas == 12:
            msg = "Columna 1 y Columna 2"
        elif columnas == 13:
            msg = "Columna 1 y Columna 3"
        elif columnas == 23:
            msg = "Columna 2 y Columna 3"
        else:
            msg = "Desconocido"

        self.bot.send_message(
            chat_id=self.chat_id,
            text=(
                f"🎰 *ENTRADA CONFIRMADA* 🎰\n"
                f"─────────────────────────\n"
                f"🎮 Juego: {self.juego}\n"
                f"🎯 Entrar en: *{msg}*\n"
                f"⚔️ Cubrir el CERO 🟢\n"
                f"🛟 Realizar {self.martingalas} Martingala(s)\n"
                f"─────────────────────────"
            )
        )
        return

    # ─────────────────────────────────────────────────────────────────────────
    # LÓGICA DE MARTINGALE
    # Evalúa el resultado de la ronda y decide si fue WIN, LOSS o EMPATE.
    # WIN    → suma victoria, actualiza racha
    # LOSS   → incrementa gale; si supera el límite, registra derrota
    # EMPATE → el cero fue protección, suma empate
    # ─────────────────────────────────────────────────────────────────────────
    def martingale(self, resultado, numero):
        if resultado == "WIN":
            print(f"✅ ¡VICTORIA! — Número: {numero}")
            self.victorias += 1
            self.racha_actual += 1
            if self.racha_actual > self.racha_max:
                self.racha_max = self.racha_actual
            
            self.historial_visual.append(f"✅ Ganada: G{self.gale_actual} (N. {numero})")
            self.bot.send_message(
                chat_id=self.chat_id,
                text=f"✅✅✅ *¡GANAMOS!* — Cayó el {numero} ✅✅✅"
            )

        elif resultado == "LOSS":
            self.gale_actual += 1

            if self.gale_actual > self.martingalas:
                print(f"🚫 DERROTA — Número: {numero}")
                self.derrotas += 1
                self.racha_actual = 0
                self.historial_visual.append(f"❌ Perdida: G{self.gale_actual-1} (N. {numero})")
                self.bot.send_message(
                    chat_id=self.chat_id,
                    text=f"🚫 *DERROTA* — Cayó el {numero} 🚫"
                )
            else:
                print(f"⚠️ Martingala {self.gale_actual}ª — Número: {numero}")
                self.alerta_gale()
                return

        elif resultado == "EMPATE":
            print(f"🟠 EMPATE (CERO) — Número: {numero}")
            self.empates += 1
            self.historial_visual.append(f"🟠 Cero: G{self.gale_actual} (N. {numero})")
            self.bot.send_message(
                chat_id=self.chat_id,
                text=f"🟠 *PROTECCIÓN* — ¡Cayó el CERO! 🟢"
            )

        # Controlar el ciclo de 10 señales
        self.gale_actual = 0
        self.analizar = True
        self.conteo_senales += 1
        
        if self.conteo_senales >= 10:
            self.resultados()
            
        self.reiniciar()
        return

    # ─────────────────────────────────────────────────────────────────────────
    # VERIFICAR RESULTADO
    # Compara el número sorteado con las columnas apostadas para determinar
    # si fue victoria, derrota o empate.
    # ─────────────────────────────────────────────────────────────────────────
    def verificar_resultado(self, numero):
        # Cayó el CERO → siempre empate (protección activa)
        if numero == 0:
            self.martingale("EMPATE", numero)
            return

        # Columnas 2 y 3 apostadas
        elif (
            self.columnas_objetivo == 23
            and (numero in self.ruleta["02"] or numero in self.ruleta["03"])
        ):
            self.martingale("WIN", numero)
            return

        # Columnas 1 y 2 apostadas
        elif (
            self.columnas_objetivo == 12
            and (numero in self.ruleta["01"] or numero in self.ruleta["02"])
        ):
            self.martingale("WIN", numero)
            return

        # Columnas 1 y 3 apostadas
        elif (
            self.columnas_objetivo == 13
            and (numero in self.ruleta["01"] or numero in self.ruleta["03"])
        ):
            self.martingale("WIN", numero)
            return

        # Ninguna columna apostada coincide
        else:
            self.martingale("LOSS", numero)
            return

    # ─────────────────────────────────────────────────────────────────────────
    # ESTRATEGIA DE CONFLUENCIA (AVANZADA)
    # Analiza repeticiones, frecuencias y ausencias para mayor seguridad.
    # ─────────────────────────────────────────────────────────────────────────
    def estrategia(self, resultados):
        # Actualizar historial interno (últimos 20)
        self.historial_resultados = resultados[0:20]
        
        print(f"🕒 {datetime.datetime.now().strftime('%H:%M:%S')} | 🎮 {self.juego} | Últimos: {resultados[0:5]}")

        # ── MODO ESPERA DE RESULTADO ──────────────────────────────────────────
        if not self.analizar:
            self.verificar_resultado(resultados[0])
            return

        # ── MODO ANÁLISIS ─────────────────────────────────────────────────────
        ultimo = resultados[0]

        # Contar consecutivos de la columna actual
        if ultimo in self.ruleta["01"]:
            self.cont_col_01 += 1
            self.cont_col_02 = 0
            self.cont_col_03 = 0
        elif ultimo in self.ruleta["02"]:
            self.cont_col_01 = 0
            self.cont_col_02 += 1
            self.cont_col_03 = 0
        elif ultimo in self.ruleta["03"]:
            self.cont_col_01 = 0
            self.cont_col_02 = 0
            self.cont_col_03 += 1
        else:
            # El cero reinicia contadores de repetición
            self.cont_col_01 = 0
            self.cont_col_02 = 0
            self.cont_col_03 = 0
            return

        # ── CÁLCULO DE SCORE DE SEGURIDAD ─────────────────────────────────────
        # Determinamos cuál es la columna candidata a romperse
        col_candidata = None
        if self.cont_col_01 >= self.aciertos: col_candidata = "01"
        elif self.cont_col_02 >= self.aciertos: col_candidata = "02"
        elif self.cont_col_03 >= self.aciertos: col_candidata = "03"

        if col_candidata:
            score = 0
            
            # 1. Puntos por repetición (más repeticiones = más score)
            consecutivos = getattr(self, f"cont_col_{col_candidata}")
            score += consecutivos * 1.5 

            # 2. Puntos por frecuencia (si la columna ha salido mucho en los últimos 20, debe parar)
            frecuencia_col = sum(1 for n in self.historial_resultados if n in self.ruleta[col_candidata])
            if frecuencia_col > 8: score += 2  # Muy caliente
            elif frecuencia_col > 6: score += 1 # Caliente

            # 3. Puntos por ausencia de las otras columnas (Gap Filter)
            # Definir las columnas a las que apostaríamos
            otras = [c for c in ["01", "02", "03"] if c != col_candidata]
            
            for col_objetivo in otras:
                ausencia = 0
                for n in resultados:
                    if n in self.ruleta[col_objetivo]: break
                    ausencia += 1
                
                if ausencia > 5: score += 2 # Muy ausente, debe salir ya
                elif ausencia > 3: score += 1

            # 4. Filtro de mercado Inestable (Zigzag)
            # Si los últimos 4 resultados son de columnas diferentes, el mercado está loco
            ultimas_cols = []
            for n in resultados[0:4]:
                for c, vals in self.ruleta.items():
                    if n in vals: ultimas_cols.append(c)
            
            if len(set(ultimas_cols)) >= 3:
                print("⚠️ Mercado inestable (Zigzag detectado). Entrada cancelada.")
                score = 0

            # ── VALIDACIÓN FINAL ──────────────────────────────────────────────
            print(f"🔍 Análisis Col.{col_candidata} | Consecutivos: {consecutivos} | Score: {score:.1f}/{self.umbral_seguridad}")

            if score >= self.umbral_seguridad:
                # Determinar código de columnas objetivo
                if col_candidata == "01": self.columnas_objetivo = 23
                elif col_candidata == "02": self.columnas_objetivo = 13
                elif col_candidata == "03": self.columnas_objetivo = 12
                
                self.enviar_senal(self.columnas_objetivo)
            return

        # ── ALERTA PRE-SEÑAL DESACTIVADA ─────────────────────────────────────
        # if (self.cont_col_01 == self.aciertos - 1 or ...):
        #     self.alerta_senal()
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # LOOP PRINCIPAL
    # Consulta la API cada segundo, detecta nuevos resultados y ejecuta la
    # estrategia. Maneja errores de conexión para no detener el bot.
    # ─────────────────────────────────────────────────────────────────────────
    def iniciar(self):
        ultimo_check = []
        print(f"🚀 Bot iniciado — Juego: {self.juego}")
        while True:
            try:
                # Simular comportamiento humano con pequeña variación
                respuesta = self.sesion.get(self.url_API, timeout=15)
                
                if respuesta.status_code != 200:
                    if respuesta.status_code == 403:
                        print(f"⚠️ Acceso restringido (403). Verificando headers...")
                    else:
                        print(f"⚠️ Servidor inestable (Status {respuesta.status_code}).")
                    time.sleep(10)
                    continue

                if not respuesta.text.strip():
                    print("⚠️ Respuesta vacía del servidor. Reintentando...")
                    time.sleep(5)
                    continue

                try:
                    datos = respuesta.json()
                except json.JSONDecodeError:
                    print(f"⚠️ Error al decodificar JSON. Respuesta recibida: {respuesta.text[:100]}...")
                    time.sleep(5)
                    continue

                resultados = []
                for item in datos:
                    try:
                        num = int(item['data']['result']['outcome']['number'])
                        resultados.append(num)
                    except (KeyError, TypeError):
                        continue

                if resultados and ultimo_check != resultados[0:10]:
                    ultimo_check = resultados[0:10]
                    self.eliminar()
                    self.estrategia(resultados)
                else:
                    # Espera normal entre consultas para no saturar
                    time.sleep(5)

            except Exception as e:
                print(f"⚠️ Error inesperado: {e}")
                time.sleep(5)
                continue


# ─── INICIO DEL BOT ──────────────────────────────────────────────────────────
script = BOT_Ruleta()
script.iniciar()
