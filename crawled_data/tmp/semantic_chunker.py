import json
import argparse
from collections import defaultdict
import uuid

def semantic_chunker(input_file_path: str, output_file_path: str, chunk_size: int = 1000, chunk_overlap: int = 200):
    """
    對清理過的 RAG JSON 資料集執行語意分塊。

    此腳本會：
    1. 讀取清理後的 JSON 檔案。
    2. 按 source_url 將所有相關的 chunks 內容合併成單一文件。
    3. 根據段落邊界（以 '\\n\\n' 分隔）對文件進行語意分塊。
    4. 將小段落組合在一起，直到達到目標 chunk_size，以確保每個 chunk 都有足夠的上下文。
    5. 產生帶有重疊部分的新 chunks，以維持 chunk 之間的連貫性。
    6. 將語意分塊後的結果寫入新的 JSON 檔案。

    Args:
        input_file_path (str): 輸入的已清理 JSON 檔案路徑。
        output_file_path (str): 語意分塊後要輸出的 JSON 檔案路徑。
        chunk_size (int): 每個 chunk 的目標大小（字元數）。
        chunk_overlap (int): 相鄰 chunks 之間的重疊大小（字元數）。
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

    # 步驟 1: 按 source_url 合併內容
    docs_by_url = defaultdict(lambda: {'content': '', 'metadata': {}})
    for chunk in data.get('chunks', []):
        url = chunk.get('source_url')
        if url:
            docs_by_url[url]['content'] += chunk.get('content', '') + "\n\n"
            if not docs_by_url[url]['metadata']:
                # 儲存第一個 chunk 的元數據作為代表
                docs_by_url[url]['metadata'] = {
                    'source_url': url,
                    'title': chunk.get('title', 'No Title')
                }
    
    print(f"發現 {len(docs_by_url)} 份獨立文件。開始進行語意分塊...")
    
    all_new_chunks = []
    
    # 步驟 2: 遍歷每份文件並進行分塊
    for url, doc in docs_by_url.items():
        full_text = doc['content']
        metadata = doc['metadata']
        
        # 根據段落進行初步分割
        paragraphs = full_text.split('\n\n')
        
        current_chunk_content = ""
        doc_chunks = []

        # 步驟 3: 將段落組合成大小合適的 chunks
        for p in paragraphs:
            p_trimmed = p.strip()
            if not p_trimmed:
                continue
            
            # 如果加上新段落會超過 chunk_size，就先儲存目前的 chunk
            if len(current_chunk_content) + len(p_trimmed) + 2 > chunk_size:
                if current_chunk_content:
                    doc_chunks.append(current_chunk_content)
                current_chunk_content = p_trimmed
            else:
                if current_chunk_content:
                    current_chunk_content += "\n\n" + p_trimmed
                else:
                    current_chunk_content = p_trimmed

        # 加入最後一個 chunk
        if current_chunk_content:
            doc_chunks.append(current_chunk_content)

        # 步驟 4: 處理重疊部分並建立最終的 chunk 結構
        chunk_index = 0
        for i, chunk_text in enumerate(doc_chunks):
            # 為了重疊，從前一個 chunk 的末尾取一些內容加到目前 chunk 的開頭
            final_chunk_text = chunk_text
            if i > 0 and chunk_overlap > 0:
                prev_chunk_text = doc_chunks[i-1]
                overlap_text = prev_chunk_text[-chunk_overlap:]
                final_chunk_text = overlap_text + " [...] " + chunk_text

            new_chunk = {
                "chunk_id": f"{uuid.uuid4()}", # 產生新的唯一 ID
                "source_url": url,
                "title": metadata.get('title'),
                "content": final_chunk_text,
                "word_count": len(final_chunk_text.split()),
                "metadata": metadata.get('metadata', {}),
                "chunk_index": chunk_index
            }
            all_new_chunks.append(new_chunk)
            chunk_index += 1

    # 建立新的輸出資料結構
    output_data = {
        "metadata": {
            "source_file": input_file_path,
            "chunking_strategy": "semantic_paragraph",
            "target_chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "total_chunks": len(all_new_chunks)
        },
        "chunks": all_new_chunks
    }

    print(f"正在將語意分塊後的資料寫入 {output_file_path}...")
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print("\n--- 語意分塊完成 ---")
    print(f"總共生成 {len(all_new_chunks)} 個新的 chunks。")
    print(f"分塊後的檔案已儲存至: {output_file_path}")


if __name__ == '__main__':
    # --- 使用方式 ---
    # 在終端機中執行此腳本:
    # python semantic_chunker.py -i cleaned_data.json -o semantic_chunks.json

    parser = argparse.ArgumentParser(description="對 RAG JSON 資料集執行語意分塊的腳本。")
    parser.add_argument("-i", "--input", required=True, help="輸入的已清理 JSON 檔案路徑。")
    parser.add_argument("-o", "--output", required=True, help="分塊後要輸出的 JSON 檔案路徑。")
    parser.add_argument("--chunk_size", type=int, default=1000, help="每個 chunk 的目標大小（字元數）。")
    parser.add_argument("--chunk_overlap", type=int, default=200, help="相鄰 chunks 之間的重疊大小（字元數）。")

    args = parser.parse_args()

    semantic_chunker(args.input, args.output, args.chunk_size, args.chunk_overlap)
