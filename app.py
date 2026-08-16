from flask import Flask, render_template, redirect, request, flash
import psycopg2
import mercadopago
import os

app = Flask(__name__)
app.secret_key = "chave_secreta_para_avisos_da_loja" # Necessário para usar mensagens de aviso (flash)

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

# ROTA 1: Abre a página secreta do formulário
@app.route('/admin')
def admin():
    return render_template('admin.html')

# ROTA 2: Recebe os dados do formulário e insere no banco Neon
@app.route('/admin/cadastrar', methods=['POST'])
def cadastrar_produto():
    try:
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        preco = request.form.get('preco')
        stock = request.form.get('stock')
        imagem_url = request.form.get('imagem_url')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO produtos (nome, descricao, preco, stock, imagem_url) VALUES (%s, %s, %s, %s, %s);",
            (nome, descricao, preco, stock, imagem_url)
        )
        conn.commit()
        cur.close()
        conn.close()

        # Retorna direto para a loja para ver o produto novo inserido
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
