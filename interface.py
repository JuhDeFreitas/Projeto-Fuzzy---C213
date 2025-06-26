import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import paho.mqtt.client as mqtt
import json
import time

# Listas de dados
tempos = []
alturas = []
tempo_atual = 0

# Parâmetros da simulação
altura_andares = {0: 0, 1: 4, 2: 7, 3: 10, 4: 13, 5: 16, 6: 19, 7: 22, 8: 25}
andar_atual = 0
altura_atual = 0

# === Funções MQTT ===
def on_connect(client, userdata, flags, rc):
    print("✅ Conectado ao broker MQTT")
    client.subscribe("C213/elevador/trajetoria")

def on_message(client, userdata, msg):
    global altura_atual, andar_atual, tempo_atual
    try:
        dados = json.loads(msg.payload.decode())

        # Esperado: {"tempo": <float>, "posicao": <float>}
        tempo = dados["tempo"]
        posicao = dados["posicao"]
        #tempo_atual = tempo_atual + tempo
        tempo_atual += 0.2

        tempos.append(tempo_atual)
        alturas.append(posicao)

        altura_atual = posicao
        novo_andar = max([k for k, v in altura_andares.items() if posicao >= v])
      

        if novo_andar != andar_atual:
            andar_atual = novo_andar + 1
            root.after(0, atualizar_indicador, andar_atual)


        print(f"📥 t={tempo_atual}, pos={posicao:}")

    except Exception as e:
        print(f"❌ Erro ao processar mensagem: {e}")

def publicar_mqtt(topico, mensagem, broker='localhost', porta=1883):
  try:
      cliente = mqtt.Client()
      cliente.connect("mqtt.eclipseprojects.io", 1883, keepalive=60)
      cliente.publish(topico, mensagem)
      cliente.disconnect()
      print(f"📡 Publicado no tópico: {mensagem}")
  except Exception as e:
      print(f"❌ Erro ao publicar MQTT: {e}")


# === Atualização do gráfico ===

def atualizar(frame):
    if len(tempos) != len(alturas) or len(tempos) == 0:
        return

    ax.clear()
    ax.plot(tempos, alturas, color='blue')
    ax.set_xlabel("Tempo (s)")
    ax.set_ylabel("Altura (m)")
    ax.set_title("Posição do Elevador")
    ax.set_ylim(-1, 28)
    ax.grid(True)

def atualizar_indicador(andar):
    index_visual = 8 - andar  # Inverte a posição visual
    for i, label in enumerate(indicadores):
        label.config(bg="orange" if i == index_visual else "lightgray")

def botao_clicado(numero_andar):
    global andar_selecionado
    andar_selecionado = numero_andar
    print(f"Andar selecionado: {andar_selecionado}")
    publicar_mqtt("C213/elevador/andar", andar_selecionado)

# === Iniciar MQTT ===
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect("mqtt.eclipseprojects.io", 1883, keepalive=60)
client.loop_start()

# === Interface ===
root = tk.Tk()
root.title("Painel do Elevador (via MQTT)")
root.geometry("710x480")
root.resizable(False, False)

titulo = tk.Label(root, text="Painel do Elevador via MQTT", font=("Arial", 18, "bold"))
titulo.pack(pady=10)

# Painel esquerdo com botões e indicadores
frame_esquerda = tk.Frame(root)
frame_esquerda.pack(side=tk.LEFT, padx=20, pady=20)

andares = [8, 7, 6, 5, 4, 3, 2, 1, 0]
estilo_botao = {"width": 4, "height": 1, "font": ("Arial", 12)}
indicadores = []

for i, andar in enumerate(andares):
    frame_linha = tk.Frame(frame_esquerda)
    frame_linha.pack()

    label_indicador = tk.Label(frame_linha, text=" ", width=2, height=1, bg="lightgray")
    label_indicador.pack(side=tk.LEFT, padx=2)
    indicadores.append(label_indicador)

    texto = "T" if andar == 0 else str(andar)
    #botao = tk.Button(frame_linha, text=texto, state="disabled", **estilo_botao)
    botao = tk.Button(frame_linha, text=texto, state="normal", command=lambda num=andar: botao_clicado(num), **estilo_botao)
    botao.pack(side=tk.LEFT)

# Painel direito com gráfico
frame_direita = tk.Frame(root)
frame_direita.pack(side=tk.RIGHT, padx=20, pady=20)

fig, ax = plt.subplots(figsize=(5, 3))
canvas = FigureCanvasTkAgg(fig, master=frame_direita)
canvas.get_tk_widget().pack()

ani = animation.FuncAnimation(fig, atualizar, interval=50)

# === Iniciar GUI ===
root.mainloop()
