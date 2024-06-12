from llama_index.llms.ollama import Ollama
from llama_parse import LlamaParse
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, PromptTemplate
from llama_index.core.embeddings import resolve_embed_model
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent
from pydantic import BaseModel
from llama_index.core.output_parsers import PydanticOutputParser
from llama_index.core.query_pipeline import QueryPipeline
from prompts import context, code_parser_template
from code_reader import code_reader
from dotenv import load_dotenv
import os
import ast
import psycopg2
import requests

load_dotenv()

# Verifique a configuração e a URL do Ollama
llm = Ollama(model="mistral", request_timeout=30.0, base_url="http://localhost:11434/api/chat")

parser = LlamaParse(result_type="markdown")

file_extractor = {".pdf": parser}
documents = SimpleDirectoryReader("./data", file_extractor=file_extractor).load_data()

embed_model = resolve_embed_model("local:BAAI/bge-m3")
vector_index = VectorStoreIndex.from_documents(documents, embed_model=embed_model)
query_engine = vector_index.as_query_engine(llm=llm)

tools = [
    QueryEngineTool(
        query_engine=query_engine,
        metadata=ToolMetadata(
            name="api_documentation",
            description="this gives documentation about code for an API. Use this for reading docs for the API",
        ),
    ),
    code_reader,
]

code_llm = Ollama(model="codellama")
agent = ReActAgent.from_tools(tools, llm=code_llm, verbose=True, context=context)

class CodeOutput(BaseModel):
    code: str
    description: str
    filename: str

parser = PydanticOutputParser(CodeOutput)
json_prompt_str = parser.format(code_parser_template)
json_prompt_tmpl = PromptTemplate(json_prompt_str)
output_pipeline = QueryPipeline(chain=[json_prompt_tmpl, llm])

# Configurações do banco de dados
access_token = 'novayork'
db_config = {
    'host': 'localhost',
    'port': 5432,
    'dbname': 'mydatabase',
    'user': 'postgres',
    'password': access_token
}

# Função para enviar dados para a API Flask
def send_to_flask_api(data):
    url = "http://localhost:5000/items"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 201:
        print('Item successfully posted to Flask API')
    else:
        print('Error posting item to Flask API:', response.status_code, response.text)

# Função para salvar dados no banco de dados PostgreSQL
def save_to_db(data):
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                code TEXT NOT NULL,
                description TEXT,
                filename TEXT
            );
        """)
        cursor.execute("INSERT INTO items (code, description, filename) VALUES (%s, %s, %s) RETURNING id;", (data['code'], data['description'], data['filename']))
        item_id = cursor.fetchone()[0]
        conn.commit()
        print(f'Item created successfully with id {item_id}')
        cursor.close()
        conn.close()
        return item_id
    except Exception as e:
        print(f'Error saving to database: {e}')
        return None

while (prompt := input("Enter a prompt (q to quit): ")) != "q":
    retries = 0
    while retries < 3:
        try:
            result = agent.query(prompt)
            next_result = output_pipeline.run(response=result)
            cleaned_json = ast.literal_eval(str(next_result).replace("assistant:", ""))
            break
        except Exception as e:
            retries += 1
            print(f"Error occurred, retry #{retries}:", e)
    if retries >= 3:
        print("Unable to process request, try again...")
        continue
    print("Code generated")
    print(cleaned_json["code"])
    print("\n\nDescription:", cleaned_json["description"])
    filename = cleaned_json["filename"]
    try:
        with open(os.path.join("output", filename), "w") as f:
            f.write(cleaned_json["code"])
        print("Saved file", filename)
    except Exception as e:
        print("Error saving file:", e)
        continue
    item_id = save_to_db(cleaned_json)
    if item_id:
        send_to_flask_api({'id': item_id, 'code': cleaned_json["code"], 'description': cleaned_json["description"], 'filename': cleaned_json["filename"]})







