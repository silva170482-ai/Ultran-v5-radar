from flask import Flask, render_template_string
import requests
import threading
import time
import pandas as pd
import pandas_ta as ta

app = Flask(__name__)

# Sua chave real da Twelve Data
API_KEY = "179ac6df87b2471e9ef378238ea4f048" 

# Reduzido para 4 ativos para não estourar o limite da API gratuita com dados históricos
ativos_lista = ["EUR/USD", "GBP/USD", "USD/JPY", "XAU/USD"]

dados_mercado = {}

def monitorar_mercado():
    global dados_mercado
    
    while True:
        novos_dados = {}
        
        for ativo in ativos_lista:
            try:
                # Agora puxamos o histórico de velas (time_series) de 1 minuto
                url = f"https://api.twelvedata.com/time_series?symbol={ativo}&interval=5min&outputsize=250&apikey={API_KEY}"
                resposta = requests.get(url).json()
                
                if "values" in resposta:
                    # Converte os dados para uma tabela do Pandas (como uma planilha)
                    df = pd.DataFrame(resposta["values"])
                    # Inverte para ordem cronológica (mais antigo primeiro)
                    df = df.iloc[::-1].reset_index(drop=True)
                    df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
                    
                    # 1. Aplicando os seus Indicadores (Ultran V5)
                    df.ta.ema(length=9, append=True)
                    df.ta.ema(length=21, append=True)
                    df.ta.ema(length=50, append=True)
                    df.ta.ema(length=200, append=True)
                    df.ta.rsi(length=14, append=True)
                    df.ta.adx(length=14, append=True)
                    df.ta.atr(length=14, append=True)
                    
                    # Pegamos os dados das duas últimas velas fechadas para comparar
                    atual = df.iloc[-1]
                    anterior = df.iloc[-2]
                    
                    preco_atual = atual['close']
                    sinal = "Aguardando Condições..."
                    cor_sinal = "#888888"
                    
                    # 2. Seus Filtros de Assertividade
                    tendenciaForte = atual['ADX_14'] > 22
                    velaForte = abs(atual['close'] - atual['open']) > (atual['ATRr_14'] * 0.3)
                    naoLateral = abs(atual['EMA_9'] - atual['EMA_21']) > (atual['close'] * 0.0001)
                    
                    tendenciaAlta = atual['EMA_9'] > atual['EMA_21'] and atual['EMA_21'] > atual['EMA_50']
                    tendenciaBaixa = atual['EMA_9'] < atual['EMA_21'] and atual['EMA_21'] < atual['EMA_50']
                    
                    # Lógica de Crossover (Cruzamento)
                    cruzou_acima = atual['EMA_9'] > atual['EMA_21'] and anterior['EMA_9'] <= anterior['EMA_21']
                    cruzou_abaixo = atual['EMA_9'] < atual['EMA_21'] and anterior['EMA_9'] >= anterior['EMA_21']
                    
                    # 3. Zonas e Gatilhos de Compra/Venda
                    compra = (tendenciaAlta and tendenciaForte and naoLateral and velaForte and 
                              atual['close'] > atual['open'] and 
                              60 < atual['RSI_14'] < 70 and cruzou_acima)
                              
                    venda = (tendenciaBaixa and tendenciaForte and naoLateral and velaForte and 
                             atual['close'] < atual['open'] and 
                             30 < atual['RSI_14'] < 40 and cruzou_abaixo)
                    
                    if compra:
                        sinal = "🟢 SINAL: COMPRA (CALL)"
                        cor_sinal = "#39FF14"
                    elif venda:
                        sinal = "🔴 SINAL: VENDA (PUT)"
                        cor_sinal = "#FF0000"
                    
                    novos_dados[ativo] = {
                        "preco": f"{preco_atual:.5f}" if "XAU" not in ativo else f"{preco_atual:.2f}",
                        "status": sinal,
                        "cor": cor_sinal
                    }
                else:
                    novos_dados[ativo] = {"preco": "Erro", "status": "Limite API", "cor": "#FFA500"}
                    
            except Exception as e:
                novos_dados[ativo] = {"preco": "Erro", "status": "Aguardando...", "cor": "#FFA500"}
                
            # Pausa de 8 segundos por ativo para puxar os históricos pesados sem estourar o limite
            time.sleep(8)
            
        dados_mercado = novos_dados
        
        # Aguarda completar 1 minuto exato para ler a próxima vela
        time.sleep(30)

html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Ultran V5 - Mercado Real</title>
    <meta http-equiv="refresh" content="15">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #ffffff; text-align: center; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; background-color: #1e1e1e; padding: 20px; border-radius: 8px; border: 1px solid #333; }
        h1 { color: #00BFFF; font-size: 24px; margin-bottom: 5px; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; background-color: #252525; }
        th, td { padding: 15px; border: 1px solid #333; text-align: center; font-size: 16px; }
        th { background-color: #333; color: #ccc; }
        .sinal-alerta { font-weight: bold; text-shadow: 0px 0px 8px currentColor; font-size: 18px; }
        .normal { font-weight: normal; color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Ultran V5 Otimizado - Radar Externo</h1>
        <p style="color: #888; font-size: 14px;">Monitorando cruzamento EMA, ADX, ATR e RSI no mercado real (Velas de 1 Minuto)</p>
        <table>
            <thead>
                <tr>
                    <th>Ativo</th>
                    <th>Cotação Fechada</th>
                    <th>Sinal Algorítmico</th>
                </tr>
            </thead>
            <tbody>
                {% for ativo, info in dados.items() %}
                <tr>
                    <td style="color: #00BFFF; font-weight: bold;">{{ ativo }}</td>
                    <td style="font-family: monospace; font-size: 18px;">{{ info.preco }}</td>
                    <td class="{% if 'SINAL' in info.status %}sinal-alerta{% else %}normal{% endif %}" style="color: {{ info.cor }};">
                        {{ info.status }}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(html_template, dados=dados_mercado)

if __name__ == "__main__":
    t = threading.Thread(target=monitorar_mercado)
    t.daemon = True
    t.start()
    app.run(host="0.0.0.0", port=5000)