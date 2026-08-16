from flask import Flask, render_template, redirect, request, flash
from werkzeug.utils import secure_filename
import psycopg2
import mercadopago
import os

app = Flask(__name__)
app.secret_key = "chave_secreta_para_avisos_da_loja"

# DEFINA A TUA SENHA DE ADMINISTRAÇÃO AQUI:
SENHA_ADMIN_DEFINIDA = "felipe123"

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_OuGyv7dWF8bU@ep-mute-bar-aqo4ff4l-pooler.c-8.us-east-1.aws.neon.tech/jipnet_loja_db?sslmode=require&channel_binding=require")
MERCADOPAGO_TOKEN = os.environ.get("MERCADOPAGO_TOKEN", "APP_USR-2105188313610547-062713-9418d808fb319a50a4623014b0a05d1d-1976170930")

sdk = mercadopago.SDK(MERCADOPAGO_TOKEN)

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route('/')
def home():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, descricao, preco, imagem_url FROM produtos ORDER BY id DESC;")
        produtos_do_banco = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('loja.html', produtos=produtos_do_banco)
    except Exception as erro:
        return f"<h1>Erro ao ligar ao banco Neon:</h1><p>{erro}</p>"

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/admin/cadastrar', methods=['POST'])
def cadastrar_produto():
    try:
        # 1. VERIFICAÇÃO DE SEGURANÇA DA SENHA
        senha_enviada = request.form.get('senha_admin')
        if senha_enviada != SENHA_ADMIN_DEFINIDA:
            return "<h1>Acesso Recusado:</h1><p>A chave de acesso inserida está incorreta!</p><br><a href='/admin'>Tentar novamente</a>"

        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        preco = request.form.get('preco')
        stock = request.form.get('stock')
        
        # 2. PROCESSO AUTOMÁTICO DE RECEBER E SALVAR A IMAGEM
        arquivo_foto = request.files.get('foto_produto')
        
        if not arquivo_foto or arquivo_foto.filename == '':
            return "<h1>Erro:</h1><p>Nenhuma imagem foi selecionada!</p>"

        # Cria a pasta 'static' se ela por acaso não existir no servidor
        pasta_static = os.path.join(app.root_path, 'static')
        if not os.path.exists(pasta_static):
            os.makedirs(pasta_static)

        # Gera um nome de arquivo seguro e salva na pasta static do projeto
        nome_arquivo_seguro = secure_filename(arquivo_foto.filename)
        caminho_completo_salvar = os.path.join(pasta_static, nome_arquivo_seguro)
        arquivo_foto.save(caminho_completo_salvar)

        # O caminho que vai para o Neon fica perfeitamente formatado como o Flask precisa
        caminho_imagem_banco = f"/static/{nome_arquivo_seguro}"

        # 3. GRAVAÇÃO NO BANCO NEON
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO produtos (nome, descricao, preco, stock, imagem_url) VALUES (%s, %s, %s, %s, %s);",
            (nome, descricao, preco, stock, caminho_imagem_banco)
        )
        conn.commit()
        cur.close()
        conn.close()

        return redirect('/')
    except Exception as e:
        return f"<h1>Erro ao salvar produto no Neon:</h1><p>{e}</p>"

@app.route('/comprar/<int:produto_id>', methods=['POST'])
def comprar(produto_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT nome, preco FROM produtos WHERE id = %s;", (produto_id,))
        produto = cur.fetchone()
        cur.close()
        conn.close()

        if not produto:
            return "Produto não encontrado", 404

        nome_produto = produto[0]
        preco_produto = float(produto[1])
        url_base = request.host_url

        preference_data = {
            "items": [
                {
                    "title": nome_produto,
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": preco_produto
                }
            ],
            "back_urls": {
                "success": url_base,
                "failure": url_base,
                "pending": url_base
            }
        }

        preference_response = sdk.preference().create(preference_data)
        
        if "response" not in preference_response or "init_point" not in preference_response["response"]:
            return f"<h1>Erro da API do Mercado Pago:</h1><pre>{preference_response}</pre>"
            
        preference = preference_response["response"]
        return redirect(preference["init_point"])

    except Exception as e:
        return f"<h1>Erro interno ao gerar pagamento:</h1><p>{e}</p>"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
