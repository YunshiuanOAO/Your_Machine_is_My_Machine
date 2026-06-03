import json
import re
import argparse

def clean_rag_data(input_file_path: str, output_file_path: str):
    """
    清理用於 RAG 的 JSON 資料集。

    這個腳本會執行以下操作：
    1. 讀取包含 chunks 的 JSON 檔案。
    2. 移除重複的、與核心內容無關的樣板文字（例如廣告、社群連結）。
    3. 過濾掉無效的頁面（例如 404 Not Found）。
    4. 移除不必要的網頁前端元數據。
    5. 將清理後的資料寫入新的 JSON 檔案。

    Args:
        input_file_path (str): 輸入的 JSON 檔案路徑。
        output_file_path (str): 清理後要輸出的 JSON 檔案路徑。
    """
    print(f"正在從 {input_file_path} 讀取資料...")
    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"錯誤：找不到檔案 {input_file_path}")
        return
    except json.JSONDecodeError:
        print(f"錯誤：檔案 {input_file_path} 格式不正確，無法解析。")
        return

    # --- 定義要移除的樣板文字模式 ---
    # 使用正規表示式，可以更彈性地匹配文字
    # re.IGNORECASE: 忽略大小寫
    # re.DOTALL: 讓 '.' 可以匹配換行符
    junk_patterns = [
        re.compile(r"macOS XPC tip Learn & practice.*?(github repos\.|Share hacking tricks by submitting PRs to the HackTricks and HackTricks Cloud github repos\.)", re.IGNORECASE | re.DOTALL),
        re.compile(r"Learn & practice.*?Support HackTricks.*?(github repos\.|Share hacking tricks by submitting PRs to the HackTricks and HackTricks Cloud github repos\.)", re.IGNORECASE | re.DOTALL),
        re.compile(r"Support HackTricks Check the subscription plans!.*?github repos\.", re.IGNORECASE | re.DOTALL),
        re.compile(r"Join the 💬 Discord group or the telegram group or follow us on Twitter 🐦 @hacktricks_live\.", re.IGNORECASE | re.DOTALL)
    ]

    # --- 定義要過濾掉的無效頁面關鍵字 ---
    filter_keywords = [
        "Page not found",
        "Document not found (404)"
    ]

    # --- 定義要移除的元數據鍵值 ---
    metadata_keys_to_remove = ["viewport", "theme-color"]

    original_chunks_count = len(data.get('chunks', []))
    cleaned_chunks = []

    print("開始清理程序...")
    for chunk in data.get('chunks', []):
        content = chunk.get('content', '')
        title = chunk.get('title', '')
        
        # 步驟 1: 過濾無效頁面
        is_invalid_page = any(keyword in title or keyword in content for keyword in filter_keywords)
        if is_invalid_page:
            continue # 跳過這個 chunk

        # 步驟 2: 移除樣板文字
        cleaned_content = content
        for pattern in junk_patterns:
            cleaned_content = pattern.sub('', cleaned_content)

        # 步驟 3: 清理前後多餘的空白和換行符
        chunk['content'] = cleaned_content.strip()
        
        # 如果清理後內容為空，也跳過
        if not chunk['content']:
            continue

        # 步驟 4: 精簡元數據
        if 'metadata' in chunk:
            for key in metadata_keys_to_remove:
                chunk['metadata'].pop(key, None) # 使用 pop 安全地移除鍵值

        cleaned_chunks.append(chunk)

    # 建立新的輸出資料結構
    new_data = {
        "metadata": data.get("metadata", {}), # 保留原始的頂層元數據
        "chunks": cleaned_chunks
    }
    # 更新元數據以反映清理後的狀態
    new_data["metadata"]["total_chunks_after_cleaning"] = len(cleaned_chunks)
    new_data["metadata"]["total_chunks_removed"] = original_chunks_count - len(cleaned_chunks)


    print(f"正在將清理後的資料寫入 {output_file_path}...")
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)

    print("\n--- 清理完成 ---")
    print(f"原始 chunk 數量: {original_chunks_count}")
    print(f"清理後 chunk 數量: {len(cleaned_chunks)}")
    print(f"已移除 chunk 數量: {original_chunks_count - len(cleaned_chunks)}")
    print(f"清理後的檔案已儲存至: {output_file_path}")


if __name__ == '__main__':
    # --- 使用方式 ---
    # 在終端機中執行此腳本:
    # python your_script_name.py -i sitemap_rag_chunks_20250731_205131.json -o cleaned_data.json

    # 建立命令列參數解析器
    parser = argparse.ArgumentParser(description="清理 RAG JSON 資料集的腳本。")
    parser.add_argument("-i", "--input", required=True, help="輸入的 JSON 檔案路徑。")
    parser.add_argument("-o", "--output", required=True, help="清理後要輸出的 JSON 檔案路徑。")

    args = parser.parse_args()

    clean_rag_data(args.input, args.output)
