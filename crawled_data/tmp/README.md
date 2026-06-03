# 網頁爬蟲 RAG 資料庫生成器

這是一個專門為 RAG (Retrieval-Augmented Generation) 系統設計的網頁爬蟲工具，能夠爬取網站的所有子目錄內容並整理成結構化資料。

## 功能特色

- 🕷️ **智能爬取**: 廣度優先搜索，支援多執行緒並發
- 🤖 **遵守規範**: 自動檢查並遵守 robots.txt
- 📝 **內容提取**: 智能提取主要內容，過濾無關資訊
- 📊 **多種格式**: 支援 JSON、CSV、Markdown 等多種輸出格式
- 🧩 **RAG 優化**: 自動分割文字塊，適合向量資料庫存儲
- 📈 **詳細日誌**: 完整的爬取過程記錄

## 安裝依賴

```bash
pip install -r requirements.txt
```

## 基本使用

### 命令行使用

```bash
# 基本爬取
python web_crawler.py https://example.com

# 自定義參數
python web_crawler.py https://example.com --depth 2 --delay 0.5 --workers 3

# 完整參數範例
python web_crawler.py https://example.com \
  --depth 3 \
  --delay 1.0 \
  --workers 5 \
  --output ./crawled_data \
  --chunk-size 1000 \
  --overlap 200
```

### 程式碼使用

```python
from web_crawler import WebCrawler

# 建立爬蟲實例
crawler = WebCrawler(
    base_url="https://example.com",
    max_depth=3,
    delay=1.0,
    max_workers=5
)

# 開始爬取
content = crawler.crawl()

# 儲存結果
crawler.save_to_json()
crawler.save_to_csv()
crawler.save_to_markdown()
crawler.save_rag_chunks(chunk_size=1000, overlap=200)
```

## 參數說明

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `url` | 要爬取的起始網址 | 必填 |
| `--depth` | 最大爬取深度 | 3 |
| `--delay` | 請求間隔時間(秒) | 1.0 |
| `--workers` | 並發執行緒數 | 5 |
| `--output` | 輸出目錄 | crawled_data |
| `--no-robots` | 忽略 robots.txt | False |
| `--chunk-size` | RAG 文字塊大小 | 1000 |
| `--overlap` | RAG 文字塊重疊大小 | 200 |

## 輸出格式

### 1. JSON 格式
完整的結構化資料，包含所有元數據：
```json
{
  "metadata": {
    "base_url": "https://example.com",
    "total_pages": 50,
    "crawl_time": "2025-07-31T10:30:00"
  },
  "pages": [
    {
      "url": "https://example.com/page1",
      "title": "頁面標題",
      "content": "頁面內容...",
      "headers": {...},
      "metadata": {...}
    }
  ]
}
```

### 2. CSV 格式
表格式資料，適合資料分析：
- url, title, content, word_count, timestamp 等欄位

### 3. Markdown 格式
人類可讀的格式，適合文檔查看：
```markdown
# 網站爬取報告

## 頁面 1: 首頁
**URL:** https://example.com
**字數:** 1250

### 內容
這裡是頁面內容...
```

### 4. RAG Chunks 格式
專為 RAG 系統優化的文字塊：
```json
{
  "metadata": {
    "total_chunks": 150,
    "chunk_size": 1000,
    "overlap": 200
  },
  "chunks": [
    {
      "chunk_id": "abc123_0",
      "source_url": "https://example.com/page1",
      "content": "文字塊內容...",
      "word_count": 1000
    }
  ]
}
```

## 爬取策略

### 1. 智能內容提取
- 自動識別主要內容區域 (main, article, .content 等)
- 移除導航、頁尾、側邊欄等無關內容
- 清理 JavaScript 和 CSS 代碼

### 2. URL 過濾
- 只爬取同域名下的頁面
- 跳過圖片、文檔、媒體檔案
- 避免管理頁面、API 端點

### 3. 禮貌爬取
- 遵守 robots.txt 規範
- 可配置請求間隔
- 並發控制避免服務器過載

### 4. 錯誤處理
- 自動重試機制
- 詳細錯誤日誌
- 優雅的異常處理

## RAG 整合建議

### 1. 向量化
將生成的文字塊使用 embedding 模型轉換為向量：
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('distiluse-base-multilingual-cased')
embeddings = model.encode(chunks)
```

### 2. 向量資料庫存儲
推薦使用的向量資料庫：
- **Chroma**: 輕量級，適合開發
- **Pinecone**: 雲端服務，擴展性好
- **Weaviate**: 功能豐富，支援多模態
- **Qdrant**: 高性能，開源

### 3. 檢索增強
```python
# 範例：使用 Chroma 進行檢索
import chromadb

client = chromadb.Client()
collection = client.create_collection("web_content")

# 添加文字塊
collection.add(
    documents=[chunk['content'] for chunk in chunks],
    metadatas=[chunk['metadata'] for chunk in chunks],
    ids=[chunk['chunk_id'] for chunk in chunks]
)

# 檢索相關內容
results = collection.query(
    query_texts=["用戶查詢"],
    n_results=5
)
```

## 最佳實踐

### 1. 選擇合適的參數
- **小型網站** (< 100 頁): depth=2, delay=0.5, workers=3
- **中型網站** (100-1000 頁): depth=3, delay=1.0, workers=5
- **大型網站** (> 1000 頁): depth=2, delay=1.5, workers=3

### 2. 內容品質控制
- 設定最小內容長度過濾
- 檢查重複內容
- 人工審核重要頁面

### 3. 增量更新
- 使用內容雜湊值檢測變更
- 定期重新爬取重要頁面
- 保留歷史版本以供比較

## 常見問題

### Q: 如何處理需要登入的頁面？
A: 可以修改 `session.headers` 添加認證資訊，或使用 Selenium 處理複雜的認證流程。

### Q: 如何爬取 JavaScript 渲染的內容？
A: 對於 SPA 應用，建議使用 Selenium 或 Playwright 替代 requests。

### Q: 如何避免被反爬蟲系統偵測？
A: 增加請求間隔、使用代理伺服器、輪換 User-Agent，遵守網站的使用條款。

### Q: 文字塊大小如何選擇？
A: 根據您的 embedding 模型和應用場景：
- 短文本檢索: 200-500 字
- 長文本理解: 800-1500 字
- 平衡方案: 1000 字左右

## 授權聲明

本工具僅供學習和研究使用，請遵守目標網站的 robots.txt 和使用條款。使用者需自行承擔使用本工具的法律責任。

## 聯絡資訊

如有問題或建議，請開啟 GitHub Issue 或聯絡開發者。
