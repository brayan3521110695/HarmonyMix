from flask import Flask, request
from controllers.mezcla_controller import index, mezclar, exportar

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# 🟢 Definir funciones con nombre (no usar lambda)
@app.route('/', endpoint='index')
def mostrar_index():
    return index(app.config['UPLOAD_FOLDER'])

@app.route('/mezclar', methods=['POST'])
def generar_mezcla():
    return mezclar(app.config['UPLOAD_FOLDER'])

@app.route('/exportar', endpoint='exportar')
def mostrar_exportar():
    return exportar()


if __name__ == '__main__':
    app.run(debug=True)
