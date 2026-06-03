"""
爬蟲配置範例檔案
修改此檔案以自定義爬蟲行為
"""

# 基本設定
CRAWLER_CONFIG = {
    # 爬取設定
    "max_depth": 3,              # 最大爬取深度
    "delay": 1.0,                # 請求間隔 (秒)
    "max_workers": 5,            # 並發執行緒數
    "timeout": 10,               # 請求超時時間 (秒)
    "respect_robots": True,      # 是否遵守 robots.txt
    
    # 內容過濾
    "min_content_length": 100,   # 最小內容長度
    "max_content_length": 50000, # 最大內容長度
    "skip_extensions": [         # 跳過的檔案副檔名
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", 
        ".ppt", ".pptx", ".zip", ".rar", ".tar", 
        ".gz", ".mp3", ".mp4", ".avi", ".jpg", 
        ".jpeg", ".png", ".gif", ".svg", ".ico"
    ],
    "skip_patterns": [           # 跳過的URL模式
        "/admin/", "/login/", "/register/", 
        "/logout/", "/search?", "/api/", "/download/"
    ],
    
    # RAG 設定
    "chunk_size": 1000,          # 文字塊大小
    "chunk_overlap": 200,        # 文字塊重疊大小
    "chunk_min_size": 50,        # 最小文字塊大小
}

# HTTP 設定
HTTP_CONFIG = {
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    },
    "verify_ssl": True,          # 是否驗證SSL憑證
    "allow_redirects": True,     # 是否允許重定向
    "max_redirects": 5,          # 最大重定向次數
}

# 內容提取設定
CONTENT_CONFIG = {
    # 主要內容選擇器 (依優先順序)
    "content_selectors": [
        "main",
        "article", 
        ".content",
        "#content",
        ".main-content",
        ".post-content",
        ".entry-content",
        ".page-content",
        ".article-content"
    ],
    
    # 要移除的標籤
    "remove_tags": [
        "script", "style", "nav", "footer", 
        "header", "aside", "advertisement",
        ".ad", ".ads", ".advertisement",
        ".sidebar", ".menu", ".navigation"
    ],
    
    # 要保留的屬性
    "keep_attrs": ["href", "src", "alt", "title"],
    
    # 標題標籤
    "header_tags": ["h1", "h2", "h3", "h4", "h5", "h6"],
}

# 輸出設定
OUTPUT_CONFIG = {
    "output_formats": ["json", "csv", "markdown", "rag_chunks"],
    "include_metadata": True,
    "include_images": True,
    "include_links": True,
    "compress_output": False,
    "timestamp_format": "%Y%m%d_%H%M%S",
}

# 網站特定設定範例
SITE_SPECIFIC_CONFIG = {
    # 範例：維基百科
    "wikipedia.org": {
        "content_selectors": ["#mw-content-text"],
        "remove_tags": ["script", "style", ".navbox", ".infobox", ".reflist"],
        "max_depth": 2,
        "delay": 2.0,
    },
    
    # 範例：新聞網站
    "news_sites": {
        "content_selectors": [".article-body", ".story-content", ".news-content"],
        "remove_tags": ["script", "style", ".related-articles", ".advertisement"],
        "max_depth": 1,
        "delay": 1.5,
    },
    
    # 範例：技術文檔
    "docs_sites": {
        "content_selectors": [".documentation", ".docs-content", "main"],
        "remove_tags": ["script", "style", ".sidebar", ".toc"],
        "max_depth": 4,
        "delay": 0.5,
    }
}

# 日誌設定
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file_logging": True,
    "console_logging": True,
    "log_file": "crawler.log",
}
