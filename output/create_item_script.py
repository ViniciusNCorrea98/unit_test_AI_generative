import psycopg2
import requests

access_token = 'X'

# Ler o conteúdo do arquivo test.py
with open('test.py') as f:
    data = f.read()

# Configurações do banco de dados
db_config = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'mydatabase',
    'user': 'postgres',
    'password': access_token
}

try:
    # Conectar ao banco de dados PostgreSQL
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()

    # Verificar se a tabela items existe e criar se não existir
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            data TEXT NOT NULL
        );
    """)

    # Inserir dados na tabela items
    cursor.execute("INSERT INTO items (data) VALUES (%s) RETURNING id;", (data,))
    item_id = cursor.fetchone()[0]
    conn.commit()
    print(f'Item created successfully with id {item_id}')

    # Enviar os dados para a API Flask
    url = "http://localhost:5000/items"
    headers = {
        'Content-Type': 'application/json'
    }
    response = requests.post(url, json={'id': item_id, 'data': data}, headers=headers)

    if response.status_code == 201:
        print('Item successfully posted to Flask API')
    else:
        print('Error posting item to Flask API:', response.status_code, response.text)

except Exception as e:
    print(f'Error: {e}')

finally:
    if cursor:
        cursor.close()
    if conn:
        conn.close()
