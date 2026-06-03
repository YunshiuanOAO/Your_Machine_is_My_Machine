#!/usr/bin/env python3
"""
測試 Claude 決策功能的簡單腳本
"""
import os
import json
import llm_handler

def test_claude_decision():
    """測試 Claude 決策功能"""
    
    # 模擬代理狀態
    agent_state = {
        "target_ip": "125.229.236.54",
        "initial_recon": {
            "rustscan_file": "scan_results_20250801_201007/rustscan_output.json",
            "dirsearch_file": "scan_results_20250801_201007/dirsearch_output.json"
        },
        "history": []
    }
    
    db_path = "./my_pentest_db"
    collection_name = "hacktricks_kb"
    
    print("[+] 開始測試 Claude 決策功能...")
    
    # 檢查必要文件是否存在
    if not os.path.exists(agent_state["initial_recon"]["rustscan_file"]):
        print(f"[!] 找不到 rustscan 結果文件: {agent_state['initial_recon']['rustscan_file']}")
        return
        
    print(f"[+] 使用掃描結果: {agent_state['initial_recon']['rustscan_file']}")
    
    # 呼叫決策函數
    try:
        decision = llm_handler.get_decision(agent_state, db_path, collection_name)
        
        if decision:
            print("[+] 成功獲得 Claude 決策!")
            print("=" * 50)
            print("完整決策結果:")
            print(json.dumps(decision, indent=2, ensure_ascii=False))
            print("=" * 50)
        else:
            print("[!] 未能獲得有效的 Claude 決策")
            
    except Exception as e:
        print(f"[!] 測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_claude_decision()