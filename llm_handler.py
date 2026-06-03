import json
import os
import anthropic
import rag_handler # 導入 RAG 處理器

def parse_rustscan_results(data: dict) -> dict:
    """
    解析 RustScan (Nmap) 的 JSON 輸出，提取關鍵服務資訊。
    """
    print("[+] 正在解析 RustScan/Nmap 結果...")
    services, host_info = [], {}
    try:
        host_data = data.get("nmaprun", {}).get("host", {})
        host = host_data[0] if isinstance(host_data, list) else host_data
        os_match = host.get("os", {}).get("osmatch", [{}])[0]
        host_info['ip'] = host.get("address", {}).get("@addr", "N/A")
        host_info['os'] = os_match.get("@name", "Unknown OS")
        # 處理單個端口或多個端口的情況
        ports_data = host.get("ports", {}).get("port", [])
        if isinstance(ports_data, dict):
            # 單個端口情況
            ports_data = [ports_data]
        elif not isinstance(ports_data, list):
            # 如果不是字典也不是列表，設為空列表
            ports_data = []
            
        for port_data in ports_data:
            service_info = port_data.get("service", {})
            product, version = service_info.get("@product", ""), service_info.get("@version", "")
            full_service_name = f"{product} {version}".strip()
            services.append({
                "port": port_data.get("@portid"), 
                "service_name": service_info.get("@name", "unknown"), 
                "full_service_name": full_service_name or service_info.get("@name", "unknown")
            })
        print(f"    - 發現 {len(services)} 個開放服務。")
        return {"host_info": host_info, "services": services}
    except Exception as e:
        print(f"[!] 解析 RustScan/Nmap 結果時發生錯誤: {e}")
        return {}

def parse_dirsearch_results(data: dict) -> dict:
    """
    解析 Dirsearch 的 JSON 輸出，並生成一個摘要。
    此函式能處理您 scan.py 產生的 dirsearch JSON 格式。
    """
    print("[+] 正在解析 Dirsearch 結果...")
    all_paths, interesting_paths_preview, notes = [], [], []
    keywords = ["admin", "login", "wp-json", "xmlrpc.php", "config", "dashboard"]
    try:
        # 您的 scan.py 產生的 JSON 是一個列表
        if not isinstance(data, list):
            print(f"[!] Dirsearch 結果格式不符預期 (應為列表)，收到的類型為: {type(data)}。")
            return {}

        for item in data:
            all_paths.append(item)
            if (item.get("status") == "200" or any(k in item.get("url", "") for k in keywords)) and len(interesting_paths_preview) < 15:
                interesting_paths_preview.append(item)

        if any("wp-" in p.get("url", "") for p in all_paths): notes.append("偵測到 WordPress 相關路徑。")
        if any("admin" in p.get("url", "") for p in all_paths): notes.append("發現多個可能的管理後台路徑。")
        
        summary = {
            "total_paths_found": len(all_paths), 
            "interesting_paths_preview": interesting_paths_preview, 
            "notes": " ".join(notes) or "未發現高價值 Web 目標。"
        }
        print(f"    - 發現 {len(all_paths)} 個網頁路徑，已生成摘要。")
        return {"web_summary": summary}
    except Exception as e:
        print(f"[!] 解析 Dirsearch 結果時發生錯誤: {e}")
        return {}

def generate_rag_queries(parsed_data: dict, history: list) -> list[str]:
    """
    根據解析後的偵察結果和歷史紀錄，生成 RAG 查詢。
    """
    print("[+] 正在根據當前情資生成 RAG 查詢...")
    queries = []
    
    # 從初始偵察生成
    for service in parsed_data.get("services", []):
        if service.get("full_service_name") and service["full_service_name"] != "unknown":
            queries.append(f"vulnerability in {service['full_service_name']}")
    
    # 從歷史紀錄的結果生成
    if history:
        last_result = history[-1]['result']['stdout']
        if "user" in last_result.lower() and "password" in last_result.lower():
             queries.append("how to perform privilege escalation on linux after getting user shell")
        if "root" in last_result.lower():
            queries.append("linux post exploitation techniques as root")

    unique_queries = list(set(queries))
    print(f"    - 已生成 {len(unique_queries)} 條獨立查詢。")
    return unique_queries

def build_prompt_for_llm(recon_summary: dict, history: list, rag_context: str) -> str:
    """
    將所有資訊打包成一個結構化的 Prompt。
    """
    print("[+] 正在建構發送給 Claude 的最終 Prompt...")
    recon_json_string = json.dumps(recon_summary, indent=2, ensure_ascii=False)
    history_string = json.dumps(history, indent=2, ensure_ascii=False) if history else "無"

    prompt_template = f"""
您是一個世界頂級的、全自動化的滲透測試決策引擎。您的任務是分析所有已知情報，規劃**下一步**的行動。

您的決策應基於以下原則：
1.  **循序漸進：** 根據已有的立足點 (foothold) 進行擴展，例如提權或橫向移動。
2.  **成功率優先：** 優先選擇有已知公開漏洞利用 (Public Exploit) 且版本匹配的服務。
3.  **影響力考量：** 優先選擇能導致更高權限的漏洞。
4.  **避免重複：** 不要重複已經執行過且失敗的行動。

---
### 已知情資

#### 1. 初始目標掃描結果摘要
```json
{recon_json_string}
```

#### 2. 已執行的行動與結果 (歷史紀錄)
```json
{history_string}
```

#### 3. 相關知識庫參考資料 (來自 RAG)
{rag_context}
---
### 您的任務

根據**所有**上述情資，規劃出**下一步最合理**的單一行動計畫。嚴格按照下面的 JSON 格式回傳您的決策。

### 輸出格式 (必須嚴格遵守)
```json
{{
  "analysis": {{
    "reasoning": "對您決策過程的簡短文字描述。解釋為什麼這是當前最合理的下一步。",
    "target_service": "您決定攻擊的目標服務名稱。",
    "vulnerability_cve": "相關的 CVE 編號，如果有的話。"
  }},
  "action_plan": {{
    "action_type": "一個預定義的動作類型，例如 'exploit', 'enumerate', 'privilege_escalation', 'lateral_movement', 'stop'。",
    "tool": "建議使用的具體工具。",
    "command": "一個完整的、可以直接複製執行的指令行。請使用 '[TARGET_IP]' 作為目標 IP 的佔位符。",
    "confidence_score": "您對此行動成功率的評分 (1-10分)。"
  }}
}}
```
如果需要LHOST參數的話設為tun0
請優先參考已知情資, 避免大量枚舉目錄
如果已知 CMS (例如 spip)，請先用 metasploit search
如果已獲得 root/SYSTEM 權限或已無計可施，請將 `action_type` 設為 `'stop'`。
"""
    return prompt_template

def call_claude_api(prompt: str) -> dict:
    """
    呼叫 Claude API。如果失敗，則印出錯誤並回傳 None。
    """
    print("\n[+] 正在將情資發送給 Claude 進行決策...")
    try:
        # 請確保您已設定 ANTHROPIC_API_KEY 環境變數
        client = anthropic.Anthropic()
        
        message = client.messages.create(
            model="claude-3-7-sonnet-latest",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text
        print("[+] 已從 Claude 收到回應。")
        
        try:
            # 首先嘗試直接解析
            return json.loads(response_text)
        except json.JSONDecodeError:
            # 如果失敗，嘗試從代碼塊中提取 JSON
            try:
                import re
                # 尋找 ```json 代碼塊
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1).strip()
                    return json.loads(json_content)
                else:
                    # 嘗試尋找任何代碼塊
                    code_match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
                    if code_match:
                        json_content = code_match.group(1).strip()
                        return json.loads(json_content)
                    else:
                        raise json.JSONDecodeError("No valid JSON found", response_text, 0)
            except json.JSONDecodeError as e:
                print("[!] Claude 回應的不是有效的 JSON 格式。")
                print(f"    - JSON 解析錯誤: {e}")
                print(f"    - 收到的原始回應: {response_text}")
                return None

    except anthropic.APIStatusError as e:
        print(f"[!] 呼叫 Claude API 時發生狀態錯誤 (Status Error): {e}")
        print(f"    - 狀態碼: {e.status_code}")
        print(f"    - 回應: {e.response}")
        return None
    except anthropic.APIConnectionError as e:
        print(f"[!] 呼叫 Claude API 時發生連線錯誤 (Connection Error): {e}")
        return None
    except Exception as e:
        print(f"[!] 呼叫 Claude API 時發生未預期的錯誤: {e}")
        return None

def get_decision(agent_state: dict, db_path: str, collection_name: str) -> dict:
    """
    核心函式：整合所有資訊，建立 Prompt，並從 LLM 獲取決策。
    """
    initial_recon_files = agent_state['initial_recon']
    history = agent_state['history']
    
    try:
        with open(initial_recon_files['rustscan_file'], 'r', encoding='utf-8') as f:
            rustscan_data = json.load(f)
        
        parsed_dirsearch = {}
        # 檢查 dirsearch 報告是否存在且非空
        if initial_recon_files.get('dirsearch_file') and os.path.exists(initial_recon_files['dirsearch_file']) and os.path.getsize(initial_recon_files['dirsearch_file']) > 0:
            with open(initial_recon_files['dirsearch_file'], 'r', encoding='utf-8') as f:
                dirsearch_data = json.load(f)
            parsed_dirsearch = parse_dirsearch_results(dirsearch_data)
    except Exception as e:
        print(f"[!] 讀取偵察檔案時發生錯誤: {e}")
        return None

    parsed_rustscan = parse_rustscan_results(rustscan_data)
    recon_summary = {**parsed_rustscan, **parsed_dirsearch}
    
    rag_queries = generate_rag_queries(recon_summary, history)
    rag_context = rag_handler.query_knowledge_base(rag_queries, db_path, collection_name)
    
    if rag_context is None:
        print("[!] RAG 知識庫查詢失敗，無法繼續決策。")
        return None
        
    final_prompt = build_prompt_for_llm(recon_summary, history, rag_context)
    
    claude_decision = call_claude_api(final_prompt)
    
    # 驗證 Claude 回應的結構
    if claude_decision is None:
        print("[!] Claude API 呼叫失敗，回傳 None")
        return None
        
    if not isinstance(claude_decision, dict):
        print(f"[!] Claude 回應不是字典格式，而是: {type(claude_decision)}")
        print(f"    - 回應內容: {claude_decision}")
        return None
        
    if "action_plan" not in claude_decision:
        print("[!] Claude 回應中缺少 'action_plan' 欄位")
        print(f"    - 回應鍵值: {list(claude_decision.keys())}")
        print(f"    - 完整回應: {claude_decision}")
        return None
        
    action_plan = claude_decision.get("action_plan", {})
    required_fields = ["action_type", "tool", "command", "confidence_score"]
    missing_fields = [field for field in required_fields if field not in action_plan]
    
    if missing_fields:
        print(f"[!] Claude 回應的 action_plan 中缺少必要欄位: {missing_fields}")
        print(f"    - 現有欄位: {list(action_plan.keys())}")
        print(f"    - 完整 action_plan: {action_plan}")
        return None
    
    print(f"[+] Claude 決策驗證成功")
    print(f"    - 行動類型: {action_plan['action_type']}")
    print(f"    - 使用工具: {action_plan['tool']}")
    print(f"    - 信心分數: {action_plan['confidence_score']}")
    
    return claude_decision
