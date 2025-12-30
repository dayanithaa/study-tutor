from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from config import CHROMA_DIR

def build_vectorstore(documents):
    embeddings = OpenAIEmbeddings()

    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )

    vectorstore.persist()
    return vectorstore
