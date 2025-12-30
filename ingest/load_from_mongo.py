from db.mongo_client import get_mongo_collection

def load_documents_from_mongo():
    collection = get_mongo_collection()
    docs = collection.find()

    texts = []
    metadatas = []

    for doc in docs:
        texts.append(doc["text"])
        metadatas.append({
            "source": doc.get("filename", "unknown"),
            "page": doc.get("page", -1)
        })

    return texts, metadatas
