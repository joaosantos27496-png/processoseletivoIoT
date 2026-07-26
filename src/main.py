import time
from machine import Pin, I2C

# -----------------------------------------------------------------------------
# CONFIGURAÇÕES DE HARDWARE & PINOS
# -----------------------------------------------------------------------------
PIN_BUTTON = 12       # Botão da porta (btn1)
PIN_SDA = 21          # SDA do MPU6050 (imu1)
PIN_SCL = 22          # SCL do MPU6050 (imu1)

# Endereço I2C do MPU6050 no Wokwi
MPU6050_ADDR = 0x68
PWR_MGMT_1 = 0x6B
TEMP_OUT_H = 0x41

# Parâmetros da lógica de monitoramento
LIMITE_TEMPO_PORTA_MS = 5000  # Tempo X = 5 segundos
DELTA_TEMP_LIMITE = 3.0       # Variação Y = 3.0 °C
INTERVALO_LEITURA_MS = 100    # Checagem a cada 100ms

# -----------------------------------------------------------------------------
# INICIALIZAÇÃO DE PERIFÉRICOS
# -----------------------------------------------------------------------------
# Botão configurado com Pull-Down interno
btn_porta = Pin(PIN_BUTTON, Pin.IN, Pin.PULL_DOWN)

# I2C para comunicação com o MPU6050
i2c = I2C(0, scl=Pin(PIN_SCL), sda=Pin(PIN_SDA), freq=400000)

def init_mpu6050():
    """Tira o MPU6050 do modo de repouso (Sleep Mode)."""
    try:
        i2c.writeto_mem(MPU6050_ADDR, PWR_MGMT_1, bytes([0]))
    except Exception as e:
        print(f"Erro ao inicializar MPU6050: {e}")

def ler_temperatura():
    """Lê os registradores de temperatura do MPU6050 e converte para Celsius."""
    try:
        data = i2c.readfrom_mem(MPU6050_ADDR, TEMP_OUT_H, 2)
        raw_temp = (data[0] << 8) | data[1]
        if raw_temp > 32767:
            raw_temp -= 65536
        # Fórmula padrão de conversão da folha de dados do MPU6050
        temp_celsius = (raw_temp / 340.0) + 36.53
        return temp_celsius
    except Exception:
        return None

# -----------------------------------------------------------------------------
# MÁQUINA DE ESTADOS E LOOP PRINCIPAL
# -----------------------------------------------------------------------------
init_mpu6050()

# Mensagem estrita exigida pelo CI na inicialização
print("Sistema de Monitoramento Inicializado")

# Variáveis de controle de tempo (Não-bloqueante)
tempo_ultimo_loop = time.ticks_ms()
tempo_porta_abriu = None

# Variáveis de estado
alarme_porta_ativo = False
alarme_temp_ativo = False

# Temperatura base inicial
temp_referencia = ler_temperatura()

while True:
    agora = time.ticks_ms()

    # Executa a checagem em intervalos regulares sem travar o processamento
    if time.ticks_diff(agora, tempo_ultimo_loop) >= INTERVALO_LEITURA_MS:
        tempo_ultimo_loop = agora

        # --- 1. LEITURA DA PORTA ---
        # btn1 == 1 -> Pressionado (Porta Fechada)
        # btn1 == 0 -> Solto (Porta Aberta)
        porta_fechada = (btn_porta.value() == 1)

        if not porta_fechada:
            if tempo_porta_abriu is None:
                tempo_porta_abriu = agora
            elif not alarme_porta_ativo:
                tempo_decorrido = time.ticks_diff(agora, tempo_porta_abriu)
                if tempo_decorrido >= LIMITE_TEMPO_PORTA_MS:
                    print("ALERTA: Porta aberta por muito tempo!")
                    alarme_porta_ativo = True
        else:
            tempo_porta_abriu = None

        # --- 2. LEITURA DE TEMPERATURA ---
        temp_atual = ler_temperatura()
        if temp_atual is not None:
            if temp_referencia is None:
                temp_referencia = temp_atual

            delta_temp = temp_atual - temp_referencia

            if delta_temp >= DELTA_TEMP_LIMITE and not alarme_temp_ativo:
                print("ALERTA: Degradacao termica detectada!")
                alarme_temp_ativo = True

        # --- 3. VERIFICAÇÃO DE RETORNO À NORMALIDADE ---
        if porta_fechada and delta_temp < DELTA_TEMP_LIMITE:
            if alarme_porta_ativo or alarme_temp_ativo:
                print("Status: Sistema Normalizado.")
                alarme_porta_ativo = False
                alarme_temp_ativo = False
                temp_referencia = temp_atual