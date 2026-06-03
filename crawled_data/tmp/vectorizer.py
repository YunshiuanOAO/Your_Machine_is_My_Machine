import json
import argparse
import chromadb
from chromadb.utils import embedding_functions
from tqdm import tqdm # 用於顯示進度條

def vectorize_and_store(input_file_path: str, db_path: str, collection_name: str):
    """
    將語意分塊後的 JSON 資料進行向量化，並存入 ChromaDB 向量資料庫。

    Args:
        input_file_path (str): 輸入的 `semanticed_*.json` 檔案路徑。
        db_path (str): ChromaDB 資料庫要儲存的資料夾路徑。
        collection_name (str): 在 ChromaDB 中要建立的集合名稱。
    """
    # --- 步驟 1: 讀取已分塊的資料 ---
    print(f"正在從 {input_file_path} 讀取資料...")
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        chunks = data.get('chunks', [])
        if not chunks:
            print("錯誤：檔案中找不到 'chunks' 或 'chunks' 為空。")
            return
    except FileNotFoundError:
        print(f"錯誤：找不到檔案 {input_file_path}")
        return
    except json.JSONDecodeError:
        print(f"錯誤：檔案 {input_file_path} 格式不正確，無法解析。")
        return

    # --- 步驟 2: 初始化 ChromaDB 和嵌入模型 ---
    # sentence-transformers 會自動下載並快取模型，第一次執行時需要一些時間。
    # 'all-MiniLM-L6-v2' 是一個輕量且高效的模型，非常適合入門。
    print("正在初始化嵌入模型 (第一次執行需要下載模型)...")
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    print(f"正在初始化 ChromaDB，資料庫將儲存在: ./{db_path}")
    # PersistentClient 會將資料庫儲存到硬碟，以便將來重複使用
    client = chromadb.PersistentClient(path=db_path)
    
    # 建立或獲取一個集合 (Collection)
    # 我們傳入 embedding_function，ChromaDB 會自動處理向量化
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=sentence_transformer_ef,
        metadata={"hnsw:space": "cosine"} # 指定使用餘弦相似度，適合文本語意搜尋
    )

    # --- 步驟 3: 準備要存入資料庫的資料 ---
    documents = []
    metadatas = []
    ids = []

    for chunk in chunks:
        # 確保每個 chunk 都有必要的欄位
        if 'content' in chunk and 'chunk_id' in chunk:
            documents.append(chunk['content'])
            metadatas.append({
                "source_url": chunk.get('source_url', 'N/A'),
                "title": chunk.get('title', 'N/A')
            })
            ids.append(chunk['chunk_id'])

    # --- 步驟 4: 分批次將資料加入資料庫 ---
    # 一次性加入大量資料可能會消耗過多記憶體，分批次是更好的做法
    batch_size = 100
    print(f"準備將 {len(documents)} 份文件分批加入資料庫...")
    
    for i in tqdm(range(0, len(documents), batch_size), desc="向量化與儲存進度"):
        batch_documents = documents[i:i + batch_size]
        batch_metadatas = metadatas[i:i + batch_size]
        batch_ids = ids[i:i + batch_size]
        
        collection.add(
            documents=batch_documents,
            metadatas=batch_metadatas,
            ids=batch_ids
        )

    print("\n--- 資料庫建構完成 ---")
    print(f"集合 '{collection_name}' 中現在有 {collection.count()} 份文件。")
    print(f"資料庫檔案儲存在 ./{db_path} 資料夾中。")

    # --- 步驟 5: 執行一個測試查詢 ---
    print("\n--- 執行測試查詢 ---")
    query_text = "how to exploit vsftpd 2.3.4 backdoor?"
    print(f"查詢問題: \"{query_text}\"")
    
    results = collection.query(
        query_texts=[query_text],
        n_results=3 # 取得最相關的 3 個結果
    )

    print("\n查詢結果:")
    for i, doc in enumerate(results['documents'][0]):
        print(f"\n--- 結果 {i+1} ---")
        print(f"相關來源: {results['metadatas'][0][i]['source_url']}")
        print(f"內容預覽: {doc[:500]}...")
        print(f"相似度分數: {results['distances'][0][i]}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="將 RAG JSON 資料向量化並存入 ChromaDB。")
    parser.add_argument("-i", "--input", default="semanticed_1.json", help="輸入的 semanticed_*.json 檔案路徑。")
    parser.add_argument("-db", "--db_path", default="hacktricks_db", help="ChromaDB 資料庫要儲存的資料夾路徑。")
    parser.add_argument("-cn", "--collection_name", default="pentest_docs", help="在 ChromaDB 中要建立的集合名稱。")

    args = parser.parse_args()
    vectorize_and_store(args.input, args.db_path, args.collection_name)
