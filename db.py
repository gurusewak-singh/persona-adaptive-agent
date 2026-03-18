import chromadb
import os
import psycopg2
from dotenv import load_dotenv
from google.genai import types
from google import genai
import numpy as np
from uuid import uuid4
from kb_preprocessing import load_knowledge_base


load_dotenv()
client = genai.Client(api_key=os.environ["GOOGLE_EMBEDDINGS_API_KEY"])

db_client = chromadb.CloudClient(
  api_key=os.environ["CHROMADB_API_KEY"],
  tenant=os.environ["CHROMADB_TENANT"],
  database=os.environ["CHROMADB_NAME"]
)


def get_db_connection():
    return psycopg2.connect(
        dbname=os.environ["CHAT_DB_NAME"],
        user=os.environ["CHAT_DB_USER"],
        password=os.environ["CHAT_DB_PASSWORD"],
        host=os.environ["CHAT_DB_HOST"],
        port=int(os.environ["CHAT_DB_PORT"])
    )



class EmbeddingFunction:
  def __call__(self, input):
    return [embed_text(text) for text in input]


def embed_text(text):
  result = client.models.embed_content(
      model="gemini-embedding-001",
      contents=text,
      config=types.EmbedContentConfig(output_dimensionality=1536)
      )
  [embedding_obj] = result.embeddings
  embedding_np = np.array(embedding_obj.values)
  normalized_embedding = embedding_np / np.linalg.norm(embedding_np)
  return normalized_embedding.tolist()

def create_collection():
  collection = db_client.create_collection(name=os.environ["CHROMADB_COLLECTION_NAME"], embedding_function=EmbeddingFunction())
# create_collection() 


def add_doc(records):
  items = records if isinstance(records, (list, tuple)) else [records]
  collection = db_client.get_collection(name=os.environ["CHROMADB_COLLECTION_NAME"])
  docs = []
  metadatas = []
  ids = []

  for item in items:
    if isinstance(item, dict):
      text = item.get("text", "")
      meta = {k: v for k, v in item.items() if k != "text"}
      doc_id = item.get("chunk_id") or f"doc-{uuid4()}"
    else:
      text = str(item)
      meta = {}
      doc_id = f"doc-{uuid4()}"

    docs.append(text)
    metadatas.append(meta)
    ids.append(doc_id)

  collection.add(ids=ids, documents=docs, metadatas=metadatas)
  return ids


def get_context(query):
  collection = db_client.get_collection(name=os.environ["CHROMADB_COLLECTION_NAME"])
  result = collection.query(query_texts=[query], n_results=3)
  return result


def get_conversation_history(session_id, limit=10):
    session_id = str(session_id)
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
          cursor.execute("""
                       SELECT role, message FROM queries
                       WHERE session_id = %s ORDER BY created_at DESC 
                       LIMIT %s
                       """, (session_id, limit)
                       )
          rows = cursor.fetchall()
        return [{"role": role, "content": message} for role, message in reversed(rows)]
    finally:
        conn.close()


def save_conversation_history(session_id, role, message, sentiment_score, escalation):
  session_id = str(session_id)
  conn = get_db_connection()
  try:
      with conn.cursor() as cursor:
        cursor.execute("""
                       INSERT INTO queries(session_id, role, message, sentiment_score, escalation)
                       VALUES(%s, %s, %s, %s, %s)
                       """,
                       (session_id, role, message, sentiment_score, escalation)
                       )
      conn.commit()
  finally:
      conn.close()

def ingest_kb_data():
   chunks = load_knowledge_base()
   add_doc(chunks)
   print(f"Added {len(chunks)} chunks")

if __name__ == "__main__":
   ingest_kb_data()