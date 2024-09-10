import random
import requests
from flask import Flask, request, jsonify, redirect
import json
from flask_cors import CORS
from datetime import datetime, timedelta
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





@app.route('/')
def hello():
    return 'Hello, World!'




# Endpoint para listar os produtos por categoria
@app.route('/products', methods=['POST'])
def get_products():
    # Recebe a categoria do JSON de entrada
    data = request.get_json()
    category = data.get('category')

    # Tenta abrir e carregar os dados do arquivo products.json
    try:
        with open('products.json', 'r') as file:
            products_data = json.load(file)
    except FileNotFoundError:
        return jsonify({"message": "Products file not found"}), 404

    # Procura a categoria especificada
    for category_entry in products_data['products_by_category']:
        if category_entry['category'] == category:
            # Embaralha a lista de produtos
            products = category_entry['products']
            random.shuffle(products)
            return jsonify(products), 200




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








@app.route('/add_product', methods=['POST'])
def add_product():
    # Recebe os dados do produto do request
    data = request.get_json()
    product_name = data['product_name']
    product_price = data['product_price']
    product_image = data['product_image']
    category = data['category']

    # Novo produto a ser adicionado
    new_product = {
        "product_name": product_name,
        "product_price": product_price,
        "product_image": product_image
    }

    # Tenta abrir e carregar os dados do arquivo products.json
    try:
        with open('products.json', 'r') as file:
            products_data = json.load(file)
    except FileNotFoundError:
        # Inicializa o arquivo se ele não existir
        initialize_products_file()
        with open('products.json', 'r') as file:
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
    with open('products.json', 'w') as file:
        json.dump(products_data, file, indent=4)

    return jsonify({"message": "Product created successfully"}), 201


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






# Função auxiliar para carregar o arquivo JSON
def load_products():
    with open('products.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

# Endpoint para listar todos os produtos
@app.route('/all_products', methods=['GET'])
def list_all_products():
    data = load_products()

    all_products = []
    # Iterar sobre todas as categorias e seus produtos
    for category in data["products_by_category"]:
        all_products.extend(category["products"])  # Adicionar todos os produtos à lista

    return jsonify(all_products)  # Retorna a lista como JSON





# SISTEMA DE BACKUP DO ARQUIVO .JSON de produtos

# Função para enviar o e-mail
def send_email(subject, body, file_path):
    from_address = "binance.letmein@gmail.com"  # Seu e-mail
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
















@app.route('/pagbank', methods=['POST'])
def pagbank():
    def convertToCents(value):
        return int(value * 100)

    # Gera um reference_id único
    reference_id = str(uuid.uuid4())

    # Calcula a data de expiração (7 dias a partir da data e hora atual)
    expiration_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S-03:00')

    # Token da API PagBank
    tokenPagBank = ("09bfed0e-65de-461e-aa00-66740ea3309972e2b4074ad584ed8221a93c184e80d2c35f-63d6-45f3-b30f"
                    "-95c85edf1c2e")

    # Url da API do Pagbank
    url = "https://sandbox.api.pagseguro.com/checkouts"

    # Recebe os dados do JSON enviado pelo front-end
    items = request.json

    # Mapeia os dados dos itens recebidos para o formato esperado pelo PagBank
    formatted_items = []
    for item in items:
        formatted_item = {
            "reference_id": reference_id,
            "name": item["product_name"],
            "quantity": 1,
            "unit_amount": convertToCents(item["product_price"]),
            "image_url": item["product_image"]
        }
        formatted_items.append(formatted_item)
    payload = {
        "customer": {
            "Name": "Seu Nome",
            "phone": {
                "country": "+55",
                "area": "11",
                "number": "978327459"
            },
            "email": "seu_email@gmail.com",
            "tax_id": "18055610576"
        },
        "shipping": {
            "type": "FIXED",
            "address_modifiable": True,
            "amount": convertToCents(9.90)
        },
        "reference_id": reference_id,
        "expiration_date": expiration_date,
        "customer_modifiable": True,
        "items": formatted_items,
        "payment_methods": [
            {
                "type": "DEBIT_CARD"
            },
            {
                "type": "PIX"
            },
            {
                "type": "CREDIT_CARD"
            }
        ],
        "soft_descriptor": "xxxx",
        "redirect_url": "https://pagseguro.uol.com.br"
    }
    headers = {
        "accept": "*/*",
        "Authorization": "Bearer " + tokenPagBank,
        "Content-type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    # Processa a resposta JSON para extrair o link com rel "PAY"
    response_data = response.json()
    pay_link = None
    for link in response_data.get("links", []):
        if link.get("rel") == "PAY":
            pay_link = link.get("href")
            break

    if pay_link:
        # Redireciona para o link de pagamento
        return pay_link
    else:
        return jsonify({"error": "Link de pagamento não encontrado"}), 400


if __name__ == '__main__':
    app.run(debug=True)
