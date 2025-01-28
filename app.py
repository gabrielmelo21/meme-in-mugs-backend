import random


import requests

from flask import Flask, request, jsonify
import json
from flask_cors import CORS
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, storage
import uuid
from dotenv import load_dotenv
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

app = Flask(__name__)
# Configurar CORS
CORS(app)

# Carregar as variáveis de ambiente do arquivo .env
load_dotenv()
# Construir o dicionário de configuração Firebase
firebase_config = {
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),  # Corrigir o caractere de nova linha
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
    "universe_domain": "googleapis.com"
}

# Escrever para um arquivo JSON temporário
with open("firebase_apikey_temp.json", "w") as json_file:
    json.dump(firebase_config, json_file)

cred = credentials.Certificate("firebase_apikey_temp.json")
# Inicializar o aplicativo Firebase


firebase_admin.initialize_app(cred, {
    'storageBucket': 'geekco-image-storage.appspot.com'
})


# Função para salvar (sobrescrever) o arquivo products.json
def save_products(data):
    try:
        with open('products.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Erro ao salvar os dados no arquivo: {e}")
        return False
    return True


# Função auxiliar para carregar o arquivo JSON
def load_products():
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print("Arquivo 'products.json' não encontrado.")
        return None
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar o arquivo JSON: {e}")
        return None
    except IOError as e:
        print(f"Erro ao ler o arquivo: {e}")
        return None


# Função para garantir que o arquivo products.json tenha a estrutura inicial
def initialize_products_file():
    # Estrutura inicial dos dados
    initial_data = {
        "products_by_category": [
            {"category": "Random", "products": []},
            {"category": "IA", "products": []},
            {"category": "Macacos", "products": []},
            {"category": "Gatos", "products": []},
            {"category": "Cachorros", "products": []},
            {"category": "Animais", "products": []},
            {"category": "MaoTsé", "products": []},
            {"category": "Politicos", "products": []}
        ]
    }

    # Cria o arquivo com a estrutura inicial se ele não existir
    try:
        with open('products.json', 'x') as file:
            json.dump(initial_data, file, indent=4)
    except FileExistsError:
        # Arquivo já existe, não faz nada
        pass


# Função para fazer upload da imagem gerada para o Firebase Storage
def upload_to_firebase(file):
    try:
        # Gerar um nome único para o arquivo usando UUID
        unique_filename = str(uuid.uuid4())

        # Referência ao bucket de armazenamento do Firebase
        bucket = storage.bucket()
        blob = bucket.blob(unique_filename)

        # Fazer o upload do arquivo
        blob.upload_from_file(file, content_type=file.content_type)

        # Tornar o arquivo público
        blob.make_public()

        print("URL da imagem foi criada: " + blob.public_url)
        # Obter a URL pública
        return blob.public_url
    except Exception as e:
        print(f"Erro ao fazer upload do arquivo: {e}")
        return None


@app.route('/')
def hello():
    return 'Hello, World!'


# Endpoint para listar os produtos por categoria
@app.route('/products', methods=['POST'])
def get_products():
    # Recebe a categoria do JSON de entrada
    data = request.get_json()
    category = data.get('category')

    if not category:
        return jsonify({"message": "Category is required"}), 400

    # Tenta abrir e carregar os dados do arquivo products.json
    try:
        with open('products.json', 'r', encoding='utf-8') as file:
            products_data = json.load(file)
    except FileNotFoundError:
        return jsonify({"message": "Products file not found"}), 404
    except json.JSONDecodeError:
        return jsonify({"message": "Error decoding products file"}), 500

    # Procura a categoria especificada
    category_entry = next((entry for entry in products_data['products_by_category'] if entry['category'] == category),
                          None)

    if category_entry:
        # Embaralha a lista de produtos
        products = category_entry['products']
        random.shuffle(products)
        return jsonify(products), 200
    else:
        return jsonify({"message": "Category not found"}), 404


# Endpoint para remover o produto pelo product_name
@app.route('/remove-product', methods=['POST'])
def remove_product():
    data = request.json
    product_name = data.get('product_name')

    # Carregar produtos do arquivo JSON
    products_data = load_products()

    # Procurar e remover o produto em todas as categorias
    for category in products_data["products_by_category"]:
        category["products"] = [product for product in category["products"] if product["product_name"] != product_name]

    # Salvar o JSON atualizado
    save_products(products_data)

    return jsonify({"message": f"Produto '{product_name}' removido com sucesso!"})


@app.route('/add_product', methods=['POST'])
def add_product():
    # Recebe os dados do produto do request
    data = request.get_json()
    product_name = data['product_name']
    product_price = data['product_price']
    product_image = data['product_image']
    category = data['category']
    product_video = data.get('product_video', False)  # Obtém o valor

    # Garante que product_video é um booleano
    product_video = str(product_video).lower() in ['true', '1', 'yes']

    # Novo produto a ser adicionado
    new_product = {
        "product_name": product_name,
        "product_price": product_price,
        "product_image": product_image,
        "product_video": product_video  # Valor convertido para booleano
    }

    # Tenta abrir e carregar os dados do arquivo products.json
    try:
        with open('products.json', 'r', encoding='utf-8') as file:
            products_data = json.load(file)
    except FileNotFoundError:
        # Inicializa o arquivo se ele não existir
        initialize_products_file()
        with open('products.json', 'r', encoding='utf-8') as file:
            products_data = json.load(file)

    # Verifica se a categoria é válida
    valid_categories = {cat['category'] for cat in products_data['products_by_category']}
    if category not in valid_categories:
        return jsonify({"message": "Invalid category"}), 400

    # Atualiza a categoria com o novo produto
    category_found = False
    for category_entry in products_data['products_by_category']:
        if category_entry['category'] == category:
            category_entry['products'].append(new_product)
            category_found = True
            break

    # Se a categoria não existir, retorna erro
    if not category_found:
        return jsonify({"message": "Category not found"}), 400

    # Salva os dados atualizados de volta no arquivo
    with open('products.json', 'w', encoding='utf-8') as file:
        json.dump(products_data, file, indent=4)

    return jsonify({"message": "Product created successfully"}), 201


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part', 400

    file = request.files['file']
    if file.filename == '':
        return 'No selected file', 400

    file_url = upload_to_firebase(file)
    if file_url:
        return file_url, 200
    else:
        return 'Erro ao fazer upload do arquivo', 500


# Endpoint para listar todos os produtos
@app.route('/all_products', methods=['GET'])
def list_all_products():
    data = load_products()

    all_products = []
    # Iterar sobre todas as categorias e seus produtos
    for category in data["products_by_category"]:
        all_products.extend(category["products"])  # Adicionar todos os produtos à lista

    return jsonify(all_products)  # Retorna a lista como JSON


# Endpoint para retornar a quantidade de produtos em cada categoria
@app.route('/products_count', methods=['GET'])
def count_products_by_category():
    products_data = load_products()

    # Dicionário para armazenar a contagem de produtos por categoria
    product_counts = {}

    # Contar produtos em cada categoria
    for category_data in products_data["products_by_category"]:
        category_name = category_data["category"]
        product_count = len(category_data["products"])
        product_counts[category_name] = product_count

    return jsonify(product_counts)


# Endpoint para adicionar "product_video": false a todos os produtos
@app.route('/add_product_video', methods=['POST'])
def add_product_video():
    data = load_products()

    # Iterar sobre todas as categorias e produtos
    for category in data.get('products_by_category', []):
        for product in category.get('products', []):
            # Adicionar o campo product_video com valor False
            product['product_video'] = False

    # Salvar as alterações no arquivo
    save_products(data)

    return jsonify({"message": "Campo 'product_video' adicionado com sucesso a todos os produtos."})


@app.route('/update_product_video', methods=['POST'])
def update_product_video():
    data = request.get_json()
    product_name = data['product_name']
    new_status = data['product_video']

    try:
        # Usa a função auxiliar para carregar os produtos
        products_data = load_products()
    except FileNotFoundError:
        return jsonify({"message": "File not found"}), 404
    except json.JSONDecodeError:
        return jsonify({"message": "Error decoding JSON"}), 400

    product_found = False

    # Procura o produto e altera o status do vídeo
    for category in products_data['products_by_category']:
        for product in category['products']:
            if product['product_name'] == product_name:
                product['product_video'] = new_status
                product_found = True
                break
        if product_found:
            break

    if not product_found:
        return jsonify({"message": "Product not found"}), 404

    # Salva os dados atualizados com codificação UTF-8
    with open('products.json', 'w', encoding='utf-8') as file:
        json.dump(products_data, file, indent=4)

    return jsonify({"message": "Product video status updated successfully"}), 200


@app.route('/consulta-cep', methods=['POST'])
def consulta_cep():
    # Recebe o CEP enviado pelo cliente (esperando um JSON com o campo "cep")
    data = request.get_json()
    cep = data.get('cep')

    # Verifica se o CEP foi fornecido
    if not cep:
        return jsonify({"error": "O campo 'cep' é obrigatório."}), 400

    # Faz uma requisição para a API do ViaCep
    url = f'https://viacep.com.br/ws/{cep}/json/'
    response = requests.get(url)

    # Se a resposta for bem-sucedida
    if response.status_code == 200:
        endereco_data = response.json()

        # Verifica se o CEP é válido
        if "erro" in endereco_data:
            return jsonify({"error": "CEP inválido."}), 400

        # Retorna os dados do endereço
        return jsonify(endereco_data)
    else:
        return jsonify({"error": "Erro ao consultar o ViaCep."}), 500


# EDITOR JSON


@app.route('/categorias', methods=['GET'])
def get_categories():
    try:
        # Abre o arquivo JSON
        with open('categorias.json', 'r', encoding='utf-8') as file:
            data = json.load(file)  # Lê o conteúdo do arquivo JSON

        return jsonify(data)  # Retorna os dados para o front-end
    except Exception as e:
        # Em caso de erro, retorna uma mensagem de erro
        return jsonify({"error": "Ocorreu um erro ao processar o arquivo", "message": str(e)}), 500


@app.route('/update_categoriasJSON', methods=['POST'])
def update_json_file2():
    try:
        # Recebe o JSON do frontend
        updated_data = request.json

        if not updated_data:
            raise ValueError("Nenhum dado recebido ou JSON inválido.")

        with open("categorias.json", 'w', encoding='utf-8') as file:
            json.dump(updated_data, file, ensure_ascii=False, indent=4)

        return jsonify({'message': 'JSON atualizado com sucesso!'})
    except Exception as e:
        # Adicione um log para ajudar a depurar
        print(f"Erro ao atualizar o JSON: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/pedidosJSON', methods=['GET'])
def get_json_file():
    try:
        with open("pedidos.json", 'r', encoding='utf-8') as file:
            data = json.load(file)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/update_pedidosJSON', methods=['POST'])
def update_json_file():
    try:
        # Recebe o JSON do frontend
        updated_data = request.json

        if not updated_data:
            raise ValueError("Nenhum dado recebido ou JSON inválido.")

        with open("pedidos.json", 'w', encoding='utf-8') as file:
            json.dump(updated_data, file, ensure_ascii=False, indent=4)

        return jsonify({'message': 'JSON atualizado com sucesso!'})
    except Exception as e:
        # Adicione um log para ajudar a depurar
        print(f"Erro ao atualizar o JSON: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/productsJSON', methods=['GET'])
def get_json_file5():
    try:
        with open("products.json", 'r', encoding='utf-8') as file:
            data = json.load(file)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/update_produtosJSON', methods=['POST'])
def update_json_file3():
    try:
        # Recebe o JSON do frontend
        updated_data = request.json

        if not updated_data:
            raise ValueError("Nenhum dado recebido ou JSON inválido.")

        with open("products.json", 'w', encoding='utf-8') as file:
            json.dump(updated_data, file, ensure_ascii=False, indent=4)

        return jsonify({'message': 'JSON atualizado com sucesso!'})
    except Exception as e:
        # Adicione um log para ajudar a depurar
        print(f"Erro ao atualizar o JSON: {e}")
        return jsonify({'error': str(e)}), 500


# Oque quero fazer , primeiro enviar o email para o cliente, dizendo que o pedido foi feito com sucesso
# depois outros emails, de compra finalizada com sucesso e que esta em andamento para entrega
# no momento que ele faz o pedido, envia um email para mim mesmo com o Json de Pedidos e o json apenas dele
#


# SISTEMA DE BACKUP DO ARQUIVO .JSON de produtos
# Endpoint para enviar o e-mail
@app.route('/send-email', methods=['POST'])
def send_email_route():
    # Caminho do arquivo JSON
    file_path = 'products.json'
    if not os.path.exists(file_path):
        return jsonify({"error": "Arquivo produtos.json não encontrado"}), 400

    # Gera a data atual no formato desejado
    current_date = datetime.now().strftime("%d/%m/%Y")  # Formato: dia/mês/ano
    subject = f"Backup do dia {current_date}"  # Título do e-mail com a data

    try:
        send_email(subject, "Backup de products.json.", file_path)
        return jsonify({"message": "E-mail enviado com sucesso!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Função para enviar o e-mail
def send_email(subject, body, file_path):
    from_address = "memeonmugs@gmail.com"  # Seu e-mail
    password = os.getenv("EMAIL_PASSWORD")  # Sua senha
    print(password)

    # Configura o servidor de e-mail (Gmail como exemplo)
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(from_address, password)

    # Cria a mensagem de e-mail
    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = "gabriel.user0100@gmail.com"
    msg['Subject'] = subject

    # Adiciona o corpo do e-mail
    msg.attach(MIMEText(body, 'plain'))

    # Anexa o arquivo JSON
    with open(file_path, 'rb') as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
        msg.attach(part)

    # Envia o e-mail
    server.sendmail(from_address, msg['To'], msg.as_string())  # Enviando para o mesmo endereço
    server.quit()


def send_email_dynamic(to, message, user_name, typeMsg):
    from_address = "memeonmugs@gmail.com"  # Seu e-mail
    password = os.getenv("EMAIL_PASSWORD")  # Senha do e-mail

    if typeMsg == 0:
        subject = "Novo Pedido realizado na Loja!"
    elif typeMsg == 1:
        subject = "Seu pedido foi registrado com sucesso!"
    else:
        subject = "Au Au Au Au"

    # Configura o servidor de e-mail (Gmail como exemplo)
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(from_address, password)

    # Cria a mensagem de e-mail
    msg = MIMEMultipart()
    msg['From'] = from_address
    msg['To'] = to
    msg['Subject'] = subject

    # Adiciona a mensagem ao corpo do e-mail
    body = f"""
    <html>
        <body>
            <h1>Olá, {user_name}!</h1>
            <p>{message}</p>
        </body>
    </html>
    """
    msg.attach(MIMEText(body, 'html'))

    # Envia o e-mail
    try:
        server.sendmail(from_address, to, msg.as_string())
        print(f"E-mail enviado para {to} com sucesso!")
    except Exception as e:
        print(f"Erro ao enviar o e-mail: {e}")
    finally:
        server.quit()

@app.route('/registrar-pedido', methods=['POST'])
def registrar_pedido():
    # Recebendo dados da requisição
    data = request.get_json()

    # Dados do cliente
    email = data.get('email')
    nome = data.get('nome')
    cep = data.get('cep')
    endereco = data.get('endereco')
    numeroCasa = data.get('numeroCasa')

    # Produtos do carrinho
    produtos = data.get('produtos')

    # Verifica se os campos estão preenchidos
    if not email or not nome or not cep or not endereco or not numeroCasa or not produtos:
        return jsonify({"message": "Todos os campos e os produtos são obrigatórios!"}), 400

    # Registro da data e hora atual do pedido
    data_hora_pedido = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Estrutura do pedido a ser salvo
    pedido = {
        'email': email,
        'nome': nome,
        'cep': cep,
        'endereco': endereco,
        'numeroCasa': numeroCasa,
        'data_hora_pedido': data_hora_pedido,
        'produtos': produtos
    }

    # Formata os produtos em HTML
    produtos_html = "<h2>Detalhes do Pedido:</h2><ul>"
    if produtos:
        for produto in produtos:
            nome = produto.get('product_name', 'Produto sem nome')
            preco = produto.get('product_price', 'Preço não informado')
            produtos_html += f"<li>{nome} - R$ {preco}</li>"
    else:
        produtos_html += "<li>Carrinho está vazio.</li>"
    produtos_html += "</ul>"

    # Formata os dados do pedido como HTML
    pedido_html = f"""
    <html>
        <body>
            <h1>Detalhes do Pedido</h1>
            <p><strong>Nome:</strong> {pedido['nome']}</p>
            <p><strong>E-mail:</strong> {pedido['email']}</p>
            <p><strong>CEP:</strong> {pedido['cep']}</p>
            <p><strong>Endereço:</strong> {pedido['endereco']}</p>
            <p><strong>Número da casa:</strong> {pedido['numeroCasa']}</p>
            <p><strong>Data e hora do pedido:</strong> {pedido['data_hora_pedido']}</p>
            {produtos_html}
        </body>
    </html>
    """

    # Envia o e-mail para o cliente
    send_email_dynamic(email, f"""
    <h1>Seu pedido foi registrado com sucesso!</h1>
    <p>Após a confirmação do pagamento, iremos preparar o envio da sua caneca.</p>
    <p><strong>Data do pedido:</strong> {pedido['data_hora_pedido']}</p>
    {pedido_html}
    """, pedido['nome'], 1)

    # Envia o e-mail para o administrador
    send_email_dynamic("memeonmugs@gmail.com", f"""
    <h1>{pedido['nome']} fez um pedido!</h1>
    <p><strong>Data do pedido:</strong> {pedido['data_hora_pedido']}</p>
    {pedido_html}
    """, "Meme", 0)

    # Verifica se o arquivo pedidos.json já existe
    if os.path.exists('pedidos.json'):
        # Se existir, lê o arquivo e adiciona o novo pedido
        with open('pedidos.json', 'r', encoding='utf-8') as file:
            pedidos = json.load(file)
    else:
        # Se não existir, cria uma nova lista de pedidos
        pedidos = []

    # Adiciona o novo pedido à lista
    pedidos.append(pedido)

    # Salva o pedido no arquivo pedidos.json
    with open('pedidos.json', 'w', encoding='utf-8') as file:
        json.dump(pedidos, file, ensure_ascii=False, indent=4)

    return jsonify({"message": "Pedido registrado com sucesso!", "pedido": pedido}), 200


if __name__ == '__main__':
    app.run(debug=True)
