from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_documents(texts, metadatas):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    documents = []
    for text, meta in zip(texts, metadatas):
        chunks = splitter.create_documents([text], metadatas=[meta])
        documents.extend(chunks)

    return documents
