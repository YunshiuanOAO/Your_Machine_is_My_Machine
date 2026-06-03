import chromadb
from chromadb.utils import embedding_functions

def query_knowledge_base(queries: list[str], db_path: str, collection_name: str) -> str:
    """
    連接到 ChromaDB 並根據查詢列表檢索相關上下文。
    """
    print(f"\n[+] 正在連接到向量資料庫: ./{db_path}")
    try:
        # 初始化嵌入模型，必須與建庫時使用的一致
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        # 連接到持久化的資料庫
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_collection(
            name=collection_name,
            embedding_function=sentence_transformer_ef
        )
    except Exception as e:
        print(f"[!] 連接資料庫或獲取集合時失敗: {e}")
        return "知識庫查詢失敗，無法獲取參考資料。"

    print(f"[+] 成功連接到集合 '{collection_name}'。正在查詢知識庫...")
    if not queries:
        print("[-] 沒有可執行的查詢，跳過 RAG 檢索。")
        return "沒有生成任何查詢，因此無 RAG 參考資料。"
        
    results = collection.query(
        query_texts=queries,
        n_results=2  # 為每個查詢獲取 2 個最相關的結果
    )
    
    # 處理並格式化查詢結果
    rag_context = ""
    unique_docs = set() # 用於避免重複的內容
    
    for i, doc_list in enumerate(results['documents']):
        for j, doc in enumerate(doc_list):
            if doc not in unique_docs:
                unique_docs.add(doc)
                source = results['metadatas'][i][j].get('source_url', 'N/A')
                rag_context += f"--- 知識庫參考資料 (來源: {source}) ---\n"
                rag_context += doc + "\n\n"
    
    if not rag_context:
        rag_context = "在知識庫中未找到與偵察結果直接相關的資料。"
        
    print("[+] 上下文檢索完成。")
    return rag_context
