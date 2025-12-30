from ingest.load_from_mongo import load_documents_from_mongo
from ingest.chunk_text import chunk_documents
from ingest.build_vectorstore import build_vectorstore
from rag.qa_chain import load_qa_chain

def ingest_pipeline():
    texts, metadatas = load_documents_from_mongo()
    documents = chunk_documents(texts, metadatas)
    build_vectorstore(documents)

def ask_question(query):
    qa_chain = load_qa_chain()
    result = qa_chain.invoke(query)

    print(result)

   # print("Answer:\n", result)
   # print("\nSources:")
   # for doc in result:
   #     print(doc.metadata)

if __name__ == "__main__":
    ingest_pipeline()

    while True:
        q = input("\nAsk a question (or 'exit'): ")
        if q.lower() == "exit":
            break
        ask_question(q)
