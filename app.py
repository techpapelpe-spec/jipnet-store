from flask import Flask, render_template, redirect, request
from werkzeug.utils import secure_filename
import psycopg2
import mercadopago
import os

app = Flask(__name__)
app.secret_key = "chave_secreta_para_avisos_da_loja"

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

# PAINEL ADMIN: Agora puxa os produtos cadastrados para listar na tabela
@app.route('/admin')
def admin():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, nome, stock, preco, imagem_url, descricao FROM produtos ORDER BY id DESC;")
        lista_produtos = cur.fetchall()
        cur.close()
        conn.close()
        return render_template('admin.html', lista_produtos=lista_produtos)
    except Exception as erro:
        return f"<h1>Erro no painel admin:</h1><p>{erro}</p>"

# CADASTRAR OU EDITAR PRODUTO
@app.route('/admin/cadastrar', methods=['POST'])
def cadastrar_produto():
    try:
        senha_enviada = request.form.get('senha_admin')
        if senha_enviada != SENHA_ADMIN_DEFINIDA:
            return "<h1>Acesso Recusado:</h1><p>A chave inserida está incorreta!</p><br><a href='/admin'>Voltar</a>"

        produto_id = request.form.get('produto_id') # Se vier preenchido, é uma Edição
        nome = request.form.get('nome')
        descricao = request.form.get('descricao')
        preco = request.form.get('preco')
        stock = request.form.get('stock')
        
        arquivo_foto = request.files.get('foto_produto')
        caminho_imagem_banco = None

        # Trata o upload se uma foto nova for enviada
        if arquivo_foto and arquivo_foto.filename != '':
            pasta_static = os.path.join(app.root_path, 'static')
            if not os.path.exists(pasta_static):
                os.makedirs(pasta_static)
            nome_arquivo_seguro = secure_filename(arquivo_foto.filename)
            arquivo_foto.save(os.path.join(pasta_static, nome_arquivo_seguro))
            caminho_imagem_banco = f"/static/{nome_arquivo_seguro}"

        conn = get_db_connection()
        cur = conn.cursor()

        if produto_id: # SE JÁ EXISTIR ID -> EDITAR (UPDATE)
            if caminho_imagem_banco:
                cur.execute(
                    "UPDATE produtos SET nome=%s, descricao=%s, preco=%s, stock=%s, imagem_url=%s WHERE id=%s;",
                    (nome, descricao, preco, stock, caminho_imagem_banco, produto_id)
                )
            else:
                cur.execute(
                    "UPDATE produtos SET nome=%s, descricao=%s, preco=%s, stock=%s WHERE id=%s;",
                    (nome, descricao, preco, stock, produto_id)
                )
        else: # SE NÃO EXISTIR ID -> NOVO CADASTRO (INSERT)
            if not caminho_imagem_banco:
                caminho_imagem_banco = "/static/mop.png" # Padrão caso falte foto
            cur.execute(
                "INSERT INTO produtos (nome, descricao, preco, stock, imagem_url) VALUES (%s, %s, %s, %s, %s);",
                (nome, descricao, preco, stock, caminho_imagem_banco)
            )
            
        conn.commit()
        cur.close()
        conn.close()
        return redirect('/admin')
    except Exception as e:
        return f"<h1>Erro ao gravar no Neon:</h1><p>{e}</p>"

# EXCLUIR PRODUTO (DELETE)
@app.route('/admin/excluir/<int:id>', methods=['POST'])
def excluir_produto(id):
    try:
        senha_enviada = request.form.get('senha_admin_excluir')
        if senha_enviada != SENHA_ADMIN_DEFINIDA:
            return "<h1>Acesso Recusado:</h1><p>A chave inserida está incorreta!</p><br><a href='/admin'>Voltar</a>"

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM produtos WHERE id = %s;", (id,))
        conn.commit()
        cur.close()
        conn.close()
        return redirect('/admin')
    except Exception as e:
        return f"<h1>Erro ao excluir do Neon:</h1><p>{e}</p>"

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
            "items": [{"title": nome_produto, "quantity": 1, "currency_id": "BRL", "unit_price": preco_produto}],
            "back_urls": {"success": url_base, "failure": url_base, "pending": url_base}
        }
        preference_response = sdk.preference().create(preference_data)
        return redirect(preference_response["response"]["init_point"])
    except Exception as e:
        return f"<h1>Erro ao gerar pagamento:</h1><p>{e}</p>"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
