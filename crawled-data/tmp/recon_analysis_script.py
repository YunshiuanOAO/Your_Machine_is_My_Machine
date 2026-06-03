import json
import argparse
import chromadb
from chromadb.utils import embedding_functions

def list_db_collections(db_path: str):
    """
    一個偵錯工具，用於連接到指定的 ChromaDB 資料庫並列出所有可用的集合。
    """
    print(f"[偵錯模式] 正在連接到資料庫: ./{db_path}")
    try:
        client = chromadb.PersistentClient(path=db_path)
        collections = client.list_collections()
        
        if not collections:
            print(f"[結果] 資料庫 '{db_path}' 中沒有任何集合。")
            print("       請先執行向量化腳本 (例如 vectorizer.py) 來建立資料庫和集合。")
        else:
            print("[結果] 在資料庫中找到以下可用的集合:")
            for collection in collections:
                print(f"  - {collection.name}")
            print("\n請使用上面列出的其中一個名稱，透過 --collection_name 參數來執行主程式。")
            
    except Exception as e:
        print(f"[錯誤] 連接到資料庫時發生問題: {e}")
        print("       請確保資料庫路徑正確，且 ChromaDB 已正確安裝。")

def parse_rustscan_results(data: dict) -> dict:
    """
    解析 RustScan (Nmap) 的 JSON 輸出，提取關鍵服務資訊。
    """
    print("[+] 正在解析 RustScan/Nmap 結果...")
    services = []
    host_info = {}
    try:
        host_data = data.get("nmaprun", {}).get("host", {})
        if isinstance(host_data, list):
            host = host_data[0] if host_data else {}
        else:
            host = host_data

        os_match = host.get("os", {}).get("osmatch", [{}])[0]
        host_info['ip'] = host.get("address", {}).get("@addr", "N/A")
        host_info['os'] = os_match.get("@name", "Unknown OS")
        
        ports = host.get("ports", {}).get("port", [])
        for port_data in ports:
            service_info = port_data.get("service", {})
            service_name = service_info.get("@name", "unknown")
            product = service_info.get("@product", "")
            version = service_info.get("@version", "")
            full_service_name = f"{product} {version}".strip()

            services.append({
                "port": port_data.get("@portid"),
                "service_name": service_name,
                "full_service_name": full_service_name if full_service_name else service_name
            })
        print(f"    - 發現 {len(services)} 個開放服務。")
        return {"host_info": host_info, "services": services}
    except (KeyError, IndexError, TypeError) as e:
        print(f"[!] 解析 RustScan/Nmap 結果時發生錯誤: {e}")
        return {}

def parse_dirsearch_results(data: dict) -> dict:
    """
    解析 Dirsearch 的 JSON 輸出，並生成一個摘要。
    """
    print("[+] 正在解析 Dirsearch 結果...")
    all_paths = []
    interesting_paths_preview = []
    notes = []
    
    status_to_watch = [200, 301, 302, 403]
    high_interest_keywords = ["admin", "login", "wp-json", "xmlrpc.php", "config", "dashboard", "license", "readme"]
    
    try:
        results = data.get("results", [])
        for item in results:
            status = item.get("status")
            if status in status_to_watch:
                path_info = {
                    "url": item.get("url"),
                    "status": status,
                    "content_length": item.get("content-length")
                }
                all_paths.append(path_info)

                if status == 200 or any(keyword in path_info["url"] for keyword in high_interest_keywords):
                    if len(interesting_paths_preview) < 15:
                         interesting_paths_preview.append(path_info)

        if any("wp-" in path["url"] for path in all_paths):
            notes.append("偵測到 WordPress 相關路徑 (例如 /wp-admin, /wp-content, /wp-json)。")
        if any("admin" in path["url"] for path in all_paths):
            notes.append("發現多個可能的管理後台路徑。")
        
        summary = {
            "total_paths_found": len(all_paths),
            "interesting_paths_preview": interesting_paths_preview,
            "notes": " ".join(notes) if notes else "未發現明顯的高價值 Web 目標。"
        }
        print(f"    - 發現 {len(all_paths)} 個網頁路徑，已生成摘要。")
        return {"web_summary": summary}
    except (KeyError, TypeError) as e:
        print(f"[!] 解析 Dirsearch 結果時發生錯誤: {e}")
        return {}

def generate_rag_queries(parsed_data: dict) -> list[str]:
    """
    根據解析後的偵察結果，生成用於 RAG 知識庫的查詢列表。
    """
    print("[+] 正在根據情資生成 RAG 查詢...")
    queries = []
    
    for service in parsed_data.get("services", []):
        if service.get("full_service_name") and service["full_service_name"] != "unknown":
            queries.append(f"vulnerability in {service['full_service_name']}")
            queries.append(f"exploit for {service['full_service_name']}")
    
    web_notes = parsed_data.get("web_summary", {}).get("notes", "")
    if "WordPress" in web_notes:
        queries.extend([
            "WordPress /wp-json/ user enumeration vulnerability",
            "WordPress xmlrpc.php vulnerabilities and attack methods",
            "common WordPress admin panel vulnerabilities"
        ])

    unique_queries = list(set(queries))
    print(f"    - 已生成 {len(unique_queries)} 條獨立查詢。")
    return unique_queries

def query_rag_database(queries: list[str], db_path: str, collection_name: str) -> str:
    """
    連接到 ChromaDB 並根據查詢列表檢索相關上下文。
    """
    print(f"\n[+] 正在連接到向量資料庫: ./{db_path}")
    try:
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_collection(
            name=collection_name,
            embedding_function=sentence_transformer_ef
        )
    except Exception as e:
        print(f"[!] 連接資料庫或獲取集合時發生未預期的錯誤: {e}")
        return "知識庫查詢失敗，無法獲取參考資料。"

    print(f"[+] 成功連接到集合 '{collection_name}'。正在查詢知識庫以獲取相關上下文...")
    if not queries:
        print("[-] 沒有可執行的查詢，跳過 RAG 檢索。")
        return "沒有生成任何查詢，因此無 RAG 參考資料。"
        
    results = collection.query(
        query_texts=queries,
        n_results=2
    )
    
    rag_context = ""
    unique_docs = set()
    
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


def build_prompt_for_llm(recon_summary: dict, rag_context: str, prompt_template: str) -> str:
    """
    將所有資訊打包進 Prompt 範本中。
    """
    print("[+] 正在建構發送給 Claude 的最終 Prompt...")
    recon_json_string = json.dumps(recon_summary, indent=2, ensure_ascii=False)
    final_prompt = prompt_template.replace("{{recon_json_string}}", recon_json_string)
    final_prompt = final_prompt.replace("{{rag_context_string}}", rag_context)
    return final_prompt

def run_main_workflow(args):
    """
    執行主分析流程
    """
    # *** 修正開始：初始化 parsed_dirsearch 為空字典 ***
    parsed_dirsearch = {}
    
    try:
        with open(args.rustscan, 'r', encoding='utf-8') as f:
            rustscan_data = json.load(f)
        
        # *** 修正：只有在提供 dirsearch 參數時才讀取和解析 ***
        if args.dirsearch:
            with open(args.dirsearch, 'r', encoding='utf-8') as f:
                dirsearch_data = json.load(f)
            parsed_dirsearch = parse_dirsearch_results(dirsearch_data)

    except FileNotFoundError as e:
        print(f"讀取檔案時發生錯誤：找不到檔案 {e.filename}")
        return
    except Exception as e:
        print(f"處理檔案時發生錯誤: {e}")
        return

    parsed_rustscan = parse_rustscan_results(rustscan_data)
    # 合併摘要，如果 parsed_dirsearch 是空的，也不會影響結果
    recon_summary = {**parsed_rustscan, **parsed_dirsearch}
    
    rag_queries = generate_rag_queries(recon_summary)
    print("\n生成的 RAG 查詢列表:")
    for q in rag_queries:
        print(f"  - {q}")

    rag_context = query_rag_database(rag_queries, args.db_path, args.collection_name)

    prompt_template = """
您是一個世界頂級的、全自動化的滲透測試決策引擎。您的任務是分析輸入的偵察情報和知識庫資料，以識別出最高優先級的攻擊向量，並以 JSON 格式輸出一個精確的、單一的行動計畫。

您的決策應基於以下原則：
1.  **成功率優先：** 優先選擇有已知公開漏洞利用 (Public Exploit) 且版本匹配的服務。
2.  **影響力考量：** 在成功率相近的情況下，優先選擇能導致遠端程式碼執行 (RCE) 或更高權限的漏洞。
3.  **單步執行：** 每次只規劃一個行動。您的目標是完成單步攻擊，而不是整個攻擊鏈。

---
### 輸入資料

#### 1. 目標掃描結果摘要
```json
{{recon_json_string}}
```

#### 2. 相關知識庫參考資料 (來自 RAG)
{{rag_context_string}}
---
### 您的任務

根據以上輸入資料，請完成以下任務：

1. **綜合分析：** 全面分析掃描結果摘要，並與知識庫資料進行比對。
2. **決策判斷：** 識別出當前最值得嘗試的**單一**攻擊向量。
3. **格式化輸出：** 嚴格按照下面的 JSON 格式回傳您的行動計畫。不要包含任何 JSON 格式以外的解釋性文字。

### 輸出格式 (必須嚴格遵守)
```json
{
  "analysis": {
    "reasoning": "對您決策過程的簡短文字描述。解釋為什麼選擇這個目標而不是其他目標。",
    "target_service": "您決定攻擊的目標服務名稱，例如 'vsftpd 2.3.4'。",
    "vulnerability_cve": "相關的 CVE 編號，如果有的話，例如 'CVE-2011-2523'。"
  },
  "action_plan": {
    "action_type": "一個預定義的動作類型，例如 'exploit', 'enumerate', 'bruteforce', 'information_gathering', 'stop'。",
    "tool": "建議使用的具體工具，例如 'metasploit', 'nmap', 'hydra'。",
    "command": "一個完整的、可以直接複製執行的指令行。",
    "confidence_score": "您對此行動成功率的評分 (1-10分)。"
  }
}
```

如果分析後認為沒有任何明顯的、高成功率的攻擊點，請將 `action_type` 設為 `'stop'`，並在 `reasoning` 中說明原因。
"""

    final_prompt = build_prompt_for_llm(recon_summary, rag_context, prompt_template)
    
    print("\n" + "="*25 + " 準備發送給 Claude 的最終 Prompt " + "="*25)
    
    if args.verbose:
        print(final_prompt)
    else:
        print("Prompt 已成功生成。使用 --verbose 參數可查看完整內容。")
        
    print("="*81)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="分析偵察結果並與 RAG 知識庫進行比對，生成最終 Prompt。")
    # *** 修正：將 rustscan 設為必要，dirsearch 設為可選 ***
    parser.add_argument("--rustscan", required=True, help="RustScan/Nmap 的 JSON 輸出檔案路徑。(必要)")
    parser.add_argument("--dirsearch", help="Dirsearch 的 JSON 輸出檔案路徑。(可選)")
    
    parser.add_argument("--db_path", default="my_pentest_db", help="ChromaDB 資料庫的路徑。")
    parser.add_argument("--collection_name", default="hacktricks_kb", help="ChromaDB 中的集合名稱。")
    parser.add_argument("--list-collections", action="store_true", help="僅列出指定資料庫中的所有集合名稱，然後結束程式。")
    parser.add_argument("-v", "--verbose", action="store_true", help="在終端機印出完整的最終 Prompt 內容。")
    
    args = parser.parse_args()

    # *** 修正：更新主流程的啟動條件 ***
    if args.list_collections:
        list_db_collections(args.db_path)
    elif args.rustscan: # 只要提供了 rustscan 檔案就執行
        run_main_workflow(args)
    else:
        # 這個 else 區塊理論上不會被觸發，因為 rustscan 是必要的
        print("錯誤：請至少提供 --rustscan 參數來執行分析。")
        parser.print_help()
