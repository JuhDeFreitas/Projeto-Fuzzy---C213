import numpy as np
import skfuzzy as fuzzy
import skfuzzy.control as ctrl
import matplotlib.pyplot as plt
import paho.mqtt.client as mqtt
import json

topico = "elevador/andar"
andar_recebido = 0

andar_setpoint = 5  # andar de destino (ex: 5º andar)
pos_setpoint = 0
pos_atual = 0

erro_atual = 0
erro_anterior = 0
delta_erro = 0

velocidade = []
condicao_parada = False
grafico = True

# Variaveis pra sistema de Inercia
k2 = 0.251287
tempo_aceleracao = 2.0
pot_max_inercial = 0.315

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Conectado ao broker MQTT")
        client.subscribe("C213/elevador/andar")
    else:
        print(f"❌ Falha na conexão MQTT, código {rc}")

def on_message(client, userdata, msg):
    global andar_recebido
    try:
        payload_str = msg.payload.decode('utf-8')  # decodifica a mensagem
        print(f"- Mensagem recebida no tópico {msg.topic}: {payload_str}")
        
        if payload_str == 'T':
            andar_recebido = 0
        else:
            andar_recebido = int(payload_str)
            
        print(f"Andar recebido via MQTT: {andar_recebido}")
    except Exception as e:
        print(f"Erro ao processar a mensagem MQTT: {e}")

    return andar_recebido 

def publicar_mqtt(topico, mensagem, broker='localhost', porta=1883):
    try:
        cliente = mqtt.Client()
        cliente.connect("mqtt.eclipseprojects.io", 1883, keepalive=60)
        cliente.publish(topico, mensagem)
        cliente.disconnect()
        #print(f"📡 Publicado no tópico: {mensagem}")
    except Exception as e:
        print(f"❌ Erro ao publicar MQTT: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("mqtt.eclipseprojects.io", 1883, 60)  
client.loop_start() 

def plt_tragetoria(trajetoria, pos_setpoint):
  # Plot da trajetória
  plt.figure()
  plt.plot(trajetoria, label='Posição (m)', color='b')
  plt.axhline(pos_setpoint, color='r', linestyle='--', label='Setpoint')
  plt.xlabel('Tempo (ciclos)')
  plt.ylabel('Posição [m]')
  plt.title('Simulação de Movimento do Elevador')
  plt.legend()
  plt.grid(True)
  plt.show()

def visualizar_variavel(var):
    var.view()
    [plt.gca().lines[i].set_linewidth(2) for i in range(len(plt.gca().lines))]
    fig = plt.gcf()
    axes = fig.gca()
    fig.set_size_inches(6, 2)
    axes.set_xlabel(xlabel=f'{var.label} [{var.unit}]')
    axes.set_ylabel(ylabel=rf'Pertinência $\mu_{{{var.membershipA}}}$')
    plt.legend(loc='upper right')
    plt.show()

#=========Variáveis Fuzzy============

# ---- Erro (posição de destino - posição atual)
Erro = ctrl.Antecedent(np.arange(0, 31, 1), 'Erro')
Erro.membershipA = 'E'
Erro.unit = 'm'
Erro['MB'] = fuzzy.trapmf(Erro.universe, [0, 0, 0, 9])
Erro['B']  = fuzzy.trimf(Erro.universe, [0, 9, 15])
Erro['M']  = fuzzy.trimf(Erro.universe, [9, 15, 21])
Erro['A']  = fuzzy.trapmf(Erro.universe, [15, 21, 32, 32])

# ---- DeltaErro (erro atual - erro anterior)
DeltaErro = ctrl.Antecedent(np.arange(-10, 10, 1), 'DeltaErro')
DeltaErro.membershipA = 'DE'
DeltaErro.unit = 'm'
DeltaErro['MN'] = fuzzy.trapmf(DeltaErro.universe, [-25, -25, -3, -2])
DeltaErro['PN'] = fuzzy.trimf(DeltaErro.universe, [-3, -2, 0])
DeltaErro['ZE'] = fuzzy.trimf(DeltaErro.universe, [-0.5, 0, 0.5])
DeltaErro['PP'] = fuzzy.trimf(DeltaErro.universe, [0, 2, 3])
DeltaErro['MP'] = fuzzy.trapmf(DeltaErro.universe, [2,3, 25, 25])

# ---- Pmotor (potência do motor - saída)
Pmotor = ctrl.Consequent(np.arange(0, 101, 1), 'Pmotor')
Pmotor.membershipA = 'P'
Pmotor.unit = '%'
Pmotor['MB']  = fuzzy.trapmf(Pmotor.universe, [0, 0, 15, 31.5]) #Inicialização
Pmotor['B']  = fuzzy.trimf(Pmotor.universe, [15, 40, 70])
Pmotor['M']  = fuzzy.trimf(Pmotor.universe, [40, 70, 90])
Pmotor['A']  = fuzzy.trapmf(Pmotor.universe, [70, 90, 100, 100])

# =========== Base de Regras =================
regras = [
    ctrl.Rule(Erro['A'] & DeltaErro['MN'], Pmotor['A']),
    ctrl.Rule(Erro['A'] & DeltaErro['PN'], Pmotor['A']),
    ctrl.Rule(Erro['A'] & DeltaErro['ZE'], Pmotor['M']),
    ctrl.Rule(Erro['A'] & DeltaErro['PP'], Pmotor['M']),
    ctrl.Rule(Erro['A'] & DeltaErro['MP'], Pmotor['B']), 

    ctrl.Rule(Erro['M'] & DeltaErro['MN'], Pmotor['A']),
    ctrl.Rule(Erro['M'] & DeltaErro['PN'], Pmotor['A']),
    ctrl.Rule(Erro['M'] & DeltaErro['ZE'], Pmotor['M']),
    ctrl.Rule(Erro['M'] & DeltaErro['PP'], Pmotor['M']),
    ctrl.Rule(Erro['M'] & DeltaErro['MP'], Pmotor['B']), 

    ctrl.Rule(Erro['B'] & DeltaErro['MN'], Pmotor['A']),
    ctrl.Rule(Erro['B'] & DeltaErro['PN'], Pmotor['A']),
    ctrl.Rule(Erro['B'] & DeltaErro['ZE'], Pmotor['M']),
    ctrl.Rule(Erro['B'] & DeltaErro['PP'], Pmotor['B']),
    ctrl.Rule(Erro['B'] & DeltaErro['MP'], Pmotor['MB']),

    ctrl.Rule(Erro['MB'] & DeltaErro['MN'], Pmotor['A']),
    ctrl.Rule(Erro['MB'] & DeltaErro['ZE'], Pmotor['MB']),
    ctrl.Rule(Erro['MB'] & DeltaErro['PN'], Pmotor['MB']),
    ctrl.Rule(Erro['MB'] & DeltaErro['PP'], Pmotor['MB']),
    ctrl.Rule(Erro['MB'] & DeltaErro['MP'], Pmotor['MB'])  
]

# ======== Sistema de controle ========== 
controle = ctrl.ControlSystem(regras)
simulador = ctrl.ControlSystemSimulation(controle)

visualizar_variavel(Erro)
visualizar_variavel(DeltaErro)
visualizar_variavel(Pmotor)

# ========== Simulação ===========
tempo = np.arange(0, 500) * 0.2  # cada ciclo é 0.2s
trajetoria = []

tempo_total = 0.0
dt = 0.2  # 200 ms
trajetoria = []
tempos = []

while True:
    if tempo_total <= tempo_aceleracao:
        # Regime de aceleração linear
        pmotor_saida = pot_max_inercial * (tempo_total / tempo_aceleracao)
        k1 = 1 if erro_atual >= 0 else -1
        pos_atual = k1 * pos_atual * 0.999 + pmotor_saida * k2
    else:
        # Controle Fuzzy PD
        if andar_recebido != andar_setpoint:
            condicao_parada = False
            grafico = True
        andar_setpoint = andar_recebido

        # Calculo dos parametros Fuzzy
        if andar_setpoint == 0:
            pos_setpoint = 0
        else:
            pos_setpoint = (andar_setpoint * 3) + 1

        erro_atual = pos_setpoint - pos_atual
        k = 1 if erro_atual >= 0 else -1
        erro_atual = abs(erro_atual)
        delta_erro = erro_anterior - erro_atual

        simulador.input['Erro'] = erro_atual
        simulador.input['DeltaErro'] = delta_erro
        simulador.compute()

        pmotor_saida = simulador.output['Pmotor'] / 100
        pos_atual = pos_atual * 0.9995 + (pmotor_saida * 0.212312 * k)
        erro_anterior = erro_atual

        if erro_atual < 0.05 and abs(delta_erro) < 0.05:
            print("\n\nCondição de parada atingida!!")
            pmotor_saida = 0
            condicao_parada = False
            if grafico:
                # plot com tempo correto
                plt.figure()
                plt.plot(tempos, trajetoria, label='Posição (m)', color='b')
                plt.axhline(pos_setpoint, color='r', linestyle='--', label='Setpoint')
                plt.xlabel('Tempo (s)')
                plt.ylabel('Posição [m]')
                plt.title('Simulação de Movimento do Elevador')
                plt.legend()
                plt.grid(True)
                plt.show()
                grafico = False

    # Enviar via MQTT
    dados = {"tempo": tempo_total, "posicao": pos_atual}
    mensagem = json.dumps(dados)
    publicar_mqtt("C213/elevador/trajetoria", mensagem)

    # Armazenar para gráfico
    tempos.append(tempo_total)
    trajetoria.append(pos_atual)

    # Incrementar tempo
    tempo_total += dt
