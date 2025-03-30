from flask import Flask

# Criando a instância do Flask
app = Flask(__name__)

# Definindo uma rota simples
@app.route('/')
def hello_world():
    return 'Olá, Mundo!'

# Iniciando o servidor
if __name__ == '__main__':
    app.run(debug=True, port=5001)
