from flask import Flask, render_template, redirect, request
import psycopg2
import mercadopago
import os

app = Flask(__name__)

# CONFIGURAÇÃO SEGURA PARA A NUVEM
# O Render vai ler o link do banco direto das configurações seguras deles
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://neondb_owner:npg_OuGyv7dWF8bU@ep-mute-bar-aqo4ff4l-pooler.c-8.us-east-1.aws.neon.tech/jipnet_loja_db?sslmode=require&channel_binding=require")

# O Render vai ler o teu Token oficial do Mercado Pago de forma escondida e segura
MERCADOPAGO_TOKEN = os.environ.get("MERCADOPAGO_TOKEN", "APP_USR-2105188313610547-062713-9418d808fb319a50a4623014b0a05d1d-1976170930")

sdk = mercadopago.SDK(MERCADOPAGO_TOKEN)

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

@app.route('/')
def home():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, descricao, preco, imagem_url FROM produtos;")
        produtos_do_banco = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('loja.html', produtos=produtos_do_banco)
    except Exception as erro:
        return f"<h1>Erro ao ligar ao banco Neon:</h1><p>{erro}</p>"

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

        # Pegamos o link oficial que o Render vai nos dar automaticamente
        # Se não encontrar (como localmente), usa o localhost
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
            # Links dinâmicos! Funcionam tanto no teu PC quanto no Render de forma automática
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
    # No Render ele usa a porta que o servidor mandar, localmente usa a 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
