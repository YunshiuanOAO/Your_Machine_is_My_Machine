#!/usr/bin/env python3
"""
Sitemap爬蟲程式 - 基於sitemap.xml爬取網站所有內容
Sitemap-based Web Crawler for RAG Database Generation

Author: Matt
Date: 2025-07-31
Purpose: 使用sitemap.xml發現並爬取網站所有頁面，生成RAG資料庫
"""

import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import time
import hashlib
import re
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Optional
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET
from collections import defaultdict


@dataclass
class WebContent:
    """網頁內容資料結構"""
    url: str
    title: str
    content: str
    headers: Dict[str, str]
    links: List[str]
    images: List[str]
    metadata: Dict[str, str]
    timestamp: str
    word_count: int
    content_hash: str
    sitemap_priority: Optional[float]
    sitemap_lastmod: Optional[str]
    sitemap_changefreq: Optional[str]


class SitemapCrawler:
    """基於Sitemap的網頁爬蟲"""
    
    def __init__(self, 
                 base_url: str,
                 sitemap_url: str = None,
                 delay: float = 1.0,
                 max_workers: int = 5,
                 max_pages: int = 500,
                 respect_robots: bool = True,
                 output_dir: str = "crawled_data",
                 min_content_length: int = 100):
        """
        初始化爬蟲
        
        Args:
            base_url: 起始網址
            sitemap_url: 指定的sitemap URL，如果提供則直接使用此sitemap
            delay: 請求間隔（秒）
            max_workers: 並發執行緒數
            max_pages: 最大爬取頁面數
            respect_robots: 是否遵守robots.txt
            output_dir: 輸出目錄
            min_content_length: 最小內容長度
        """
        self.base_url = base_url.rstrip('/')
        parsed_url = urlparse(base_url)
        self.domain = parsed_url.netloc
        self.scheme = parsed_url.scheme
        self.specified_sitemap_url = sitemap_url
        
        self.delay = delay
        self.max_workers = max_workers
        self.max_pages = max_pages
        self.respect_robots = respect_robots
        self.output_dir = Path(output_dir)
        self.min_content_length = min_content_length
        
        # 建立輸出目錄
        self.output_dir.mkdir(exist_ok=True)
        
        # 設定日誌
        self._setup_logging()
        
        # 初始化變數
        self.crawled_content: List[WebContent] = []
        self.session = requests.Session()
        self.robots_parser = None
        self.sitemap_urls: List[Dict] = []
        
        # 設定HTTP headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        # 檢查robots.txt
        if self.respect_robots:
            self._check_robots_txt()
    
    def _setup_logging(self):
        """設定日誌系統"""
        log_file = self.output_dir / "sitemap_crawler.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _check_robots_txt(self):
        """檢查並解析robots.txt"""
        try:
            robots_url = f"{self.scheme}://{self.domain}/robots.txt"
            self.robots_parser = RobotFileParser()
            self.robots_parser.set_url(robots_url)
            self.robots_parser.read()
            self.logger.info(f"已載入robots.txt: {robots_url}")
        except Exception as e:
            self.logger.warning(f"無法載入robots.txt: {e}")
            self.robots_parser = None
    
    def _can_fetch(self, url: str) -> bool:
        """檢查是否可以爬取該URL"""
        if not self.robots_parser:
            return True
        
        try:
            return self.robots_parser.can_fetch('*', url)
        except Exception:
            return True
    
    def discover_sitemaps(self) -> List[str]:
        """自動發現sitemap文件"""
        # 如果指定了sitemap URL，則直接使用
        if self.specified_sitemap_url:
            self.logger.info(f"使用指定的sitemap URL: {self.specified_sitemap_url}")
            return [self.specified_sitemap_url]
        
        sitemap_urls = []
        
        # 常見的sitemap位置
        common_sitemap_paths = [
            '/sitemap.xml',
            '/sitemap_index.xml',
            '/sitemaps.xml',
            '/sitemap/sitemap.xml',
            '/sitemaps/sitemap.xml'
        ]
        
        # 首先檢查robots.txt中的sitemap
        if self.robots_parser:
            try:
                robots_url = f"{self.scheme}://{self.domain}/robots.txt"
                response = self.session.get(robots_url)
                if response.status_code == 200:
                    for line in response.text.split('\n'):
                        if line.lower().startswith('sitemap:'):
                            sitemap_url = line.split(':', 1)[1].strip()
                            sitemap_urls.append(sitemap_url)
                            self.logger.info(f"從robots.txt發現sitemap: {sitemap_url}")
            except Exception as e:
                self.logger.warning(f"無法從robots.txt讀取sitemap: {e}")
        
        # 檢查常見位置
        for path in common_sitemap_paths:
            sitemap_url = f"{self.scheme}://{self.domain}{path}"
            try:
                response = self.session.head(sitemap_url, timeout=10)
                if response.status_code == 200:
                    sitemap_urls.append(sitemap_url)
                    self.logger.info(f"發現sitemap: {sitemap_url}")
            except:
                continue
        
        if not sitemap_urls:
            self.logger.warning("未發現任何sitemap文件，將使用默認sitemap.xml")
            sitemap_urls = [f"{self.scheme}://{self.domain}/sitemap.xml"]
        
        return list(set(sitemap_urls))  # 去重
    
    def parse_sitemap(self, sitemap_url: str) -> List[Dict]:
        """解析sitemap文件"""
        urls = []
        
        try:
            self.logger.info(f"解析sitemap: {sitemap_url}")
            response = self.session.get(sitemap_url, timeout=15)
            response.raise_for_status()
            
            # 解析XML
            root = ET.fromstring(response.content)
            
            # 動態獲取命名空間
            namespace = ''
            if root.tag.startswith('{'):
                namespace = root.tag.split('}')[0] + '}'
            
            # 檢查是否為sitemap index
            sitemapindex_elements = root.findall('.//{0}sitemap'.format(namespace))
            
            if sitemapindex_elements:
                # 這是一個sitemap index，包含多個sitemap
                self.logger.info(f"發現sitemap index，包含 {len(sitemapindex_elements)} 個子sitemap")
                for sitemap_elem in sitemapindex_elements:
                    loc_elem = sitemap_elem.find('{0}loc'.format(namespace))
                    if loc_elem is not None:
                        sub_sitemap_url = loc_elem.text.strip()
                        # 遞歸解析子sitemap
                        sub_urls = self.parse_sitemap(sub_sitemap_url)
                        urls.extend(sub_urls)
            else:
                # 這是一個普通的sitemap，包含URL列表
                url_elements = root.findall('.//{0}url'.format(namespace))
                
                for url_elem in url_elements:
                    url_data = {}
                    
                    # 提取URL
                    loc_elem = url_elem.find('{0}loc'.format(namespace))
                    if loc_elem is not None:
                        url_data['url'] = loc_elem.text.strip()
                    else:
                        continue
                    
                    # 提取優先級
                    priority_elem = url_elem.find('{0}priority'.format(namespace))
                    if priority_elem is not None:
                        try:
                            url_data['priority'] = float(priority_elem.text.strip())
                        except:
                            url_data['priority'] = None
                    else:
                        url_data['priority'] = None
                    
                    # 提取最後修改時間
                    lastmod_elem = url_elem.find('{0}lastmod'.format(namespace))
                    if lastmod_elem is not None:
                        url_data['lastmod'] = lastmod_elem.text.strip()
                    else:
                        url_data['lastmod'] = None
                    
                    # 提取變更頻率
                    changefreq_elem = url_elem.find('{0}changefreq'.format(namespace))
                    if changefreq_elem is not None:
                        url_data['changefreq'] = changefreq_elem.text.strip()
                    else:
                        url_data['changefreq'] = None
                    
                    urls.append(url_data)
                
                self.logger.info(f"從sitemap解析到 {len(urls)} 個URL")
        
        except Exception as e:
            self.logger.error(f"解析sitemap失敗 {sitemap_url}: {e}")
        
        return urls
    
    def load_sitemap_urls(self) -> List[Dict]:
        """載入所有sitemap中的URL"""
        all_urls = []
        
        # 發現sitemap文件
        sitemap_files = self.discover_sitemaps()
        
        for sitemap_file in sitemap_files:
            urls = self.parse_sitemap(sitemap_file)
            all_urls.extend(urls)
        
        # 去重並過濾
        seen_urls = set()
        filtered_urls = []
        
        for url_data in all_urls:
            url = url_data['url']
            if url not in seen_urls and self._is_valid_url(url):
                seen_urls.add(url)
                filtered_urls.append(url_data)
        
        # 按優先級和最後修改時間排序
        filtered_urls.sort(key=lambda x: (
            -(x['priority'] or 0.5),  # 優先級高的在前
            x['lastmod'] or '1900-01-01'  # 最新修改的在前
        ), reverse=True)
        
        self.logger.info(f"總共發現 {len(filtered_urls)} 個有效URL")
        
        # 限制數量
        if len(filtered_urls) > self.max_pages:
            filtered_urls = filtered_urls[:self.max_pages]
            self.logger.info(f"限制為前 {self.max_pages} 個URL")
        
        return filtered_urls
    
    def _is_valid_url(self, url: str) -> bool:
        """檢查URL是否有效"""
        try:
            parsed = urlparse(url)
            
            # 檢查是否為有效的URL格式
            if not parsed.netloc or not parsed.scheme:
                return False
            
            # 只爬取同一域名
            if parsed.netloc != self.domain:
                return False
            
            # 跳過特定檔案類型
            skip_extensions = {
                '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                '.zip', '.rar', '.tar', '.gz', '.7z',
                '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv',
                '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', '.bmp',
                '.css', '.js', '.xml', '.json', '.txt', '.log'
            }
            
            path_lower = parsed.path.lower()
            if any(path_lower.endswith(ext) for ext in skip_extensions):
                return False
            
            # 跳過特定模式
            skip_patterns = [
                '/admin', '/login', '/register', '/logout',
                '/api/', '/download/', '/upload/',
                '?search=', '?q=', '?query='
            ]
            
            url_lower = url.lower()
            if any(pattern in url_lower for pattern in skip_patterns):
                return False
            
            return True
            
        except Exception:
            return False
    
    def _extract_content(self, soup: BeautifulSoup) -> Dict[str, any]:
        """從BeautifulSoup物件提取內容"""
        # 移除不需要的標籤
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'advertisement']):
            tag.decompose()
        
        # 提取標題
        title = soup.find('title')
        title_text = title.get_text().strip() if title else ""
        
        # 提取主要內容
        content_selectors = [
            'main', 'article', '[role="main"]',
            '.main-content', '#main-content', '.content', '#content',
            '.post-content', '.entry-content', '.page-content',
            '.article-content', '.post', '.entry', '.article'
        ]
        
        main_content = None
        for selector in content_selectors:
            try:
                main_content = soup.select_one(selector)
                if main_content and len(main_content.get_text().strip()) > self.min_content_length:
                    break
            except:
                continue
        
        if not main_content:
            main_content = soup.find('body') or soup
            # 移除不需要的元素
            for unwanted in main_content.find_all(['nav', 'aside', '.sidebar', '.navigation', '.menu']):
                unwanted.decompose()
        
        # 提取文字內容
        text_content = main_content.get_text() if main_content else ""
        text_content = re.sub(r'\n\s*\n', '\n\n', text_content)
        text_content = re.sub(r' +', ' ', text_content)
        text_content = text_content.strip()
        
        # 提取連結
        links = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            if href:
                absolute_url = urljoin(self.base_url, href)
                if self._is_valid_url(absolute_url):
                    links.append(absolute_url)
        
        # 提取圖片
        images = []
        for img in soup.find_all('img', src=True):
            src = img.get('src', '').strip()
            if src:
                absolute_url = urljoin(self.base_url, src)
                images.append(absolute_url)
        
        # 提取meta資訊
        metadata = {}
        for meta in soup.find_all('meta'):
            name = meta.get('name') or meta.get('property')
            content = meta.get('content')
            if name and content:
                metadata[name] = content
        
        # 提取headers資訊
        headers = {}
        for i in range(1, 7):
            header_tags = soup.find_all(f'h{i}')
            if header_tags:
                headers[f'h{i}'] = [tag.get_text().strip() for tag in header_tags]
        
        return {
            'title': title_text,
            'content': text_content,
            'links': links,
            'images': images,
            'headers': headers,
            'metadata': metadata
        }
    
    def _crawl_page(self, url_data: Dict) -> Optional[WebContent]:
        """爬取單一頁面"""
        url = url_data['url']
        
        try:
            # 檢查robots.txt
            if not self._can_fetch(url):
                self.logger.warning(f"Robots.txt禁止爬取: {url}")
                return None
            
            self.logger.info(f"爬取頁面: {url}")
            
            # 發送請求
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # 檢查內容類型
            content_type = response.headers.get('content-type', '').lower()
            if 'text/html' not in content_type:
                self.logger.warning(f"非HTML內容: {url} ({content_type})")
                return None
            
            # 解析HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 提取內容
            extracted = self._extract_content(soup)
            
            # 檢查內容是否有意義
            if len(extracted['content']) < self.min_content_length:
                self.logger.warning(f"內容過短，跳過: {url} ({len(extracted['content'])} 字元)")
                return None
            
            # 建立內容物件
            content = WebContent(
                url=url,
                title=extracted['title'],
                content=extracted['content'],
                headers=extracted['headers'],
                links=extracted['links'],
                images=extracted['images'],
                metadata=extracted['metadata'],
                timestamp=datetime.now().isoformat(),
                word_count=len(extracted['content'].split()),
                content_hash=hashlib.md5(extracted['content'].encode()).hexdigest(),
                sitemap_priority=url_data.get('priority'),
                sitemap_lastmod=url_data.get('lastmod'),
                sitemap_changefreq=url_data.get('changefreq')
            )
            
            self.logger.info(f"成功爬取: {url} ({content.word_count} 字)")
            return content
            
        except Exception as e:
            self.logger.error(f"爬取失敗 {url}: {e}")
            return None
    
    def crawl(self) -> List[WebContent]:
        """開始爬取"""
        self.logger.info(f"開始基於sitemap爬取網站: {self.base_url}")
        
        # 載入sitemap中的URL
        self.sitemap_urls = self.load_sitemap_urls()
        
        if not self.sitemap_urls:
            self.logger.error("未找到任何可爬取的URL")
            return []
        
        self.logger.info(f"準備爬取 {len(self.sitemap_urls)} 個頁面")
        
        # 並發爬取
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {
                executor.submit(self._crawl_page, url_data): url_data
                for url_data in self.sitemap_urls
            }
            
            completed = 0
            for future in as_completed(future_to_url):
                url_data = future_to_url[future]
                completed += 1
                
                try:
                    content = future.result()
                    if content:
                        self.crawled_content.append(content)
                    
                    # 顯示進度
                    if completed % 10 == 0 or completed == len(self.sitemap_urls):
                        self.logger.info(f"進度: {completed}/{len(self.sitemap_urls)} ({completed/len(self.sitemap_urls)*100:.1f}%)")
                    
                except Exception as e:
                    self.logger.error(f"處理 {url_data['url']} 時發生錯誤: {e}")
                
                # 延遲
                if self.delay > 0:
                    time.sleep(self.delay)
        
        self.logger.info(f"爬取完成，共成功處理 {len(self.crawled_content)} 個頁面")
        return self.crawled_content
    
    def save_to_json(self, filename: str = None) -> str:
        """儲存為JSON格式"""
        if not filename:
            filename = f"sitemap_crawled_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.output_dir / filename
        
        data = {
            'metadata': {
                'base_url': self.base_url,
                'crawl_time': datetime.now().isoformat(),
                'total_pages': len(self.crawled_content),
                'total_sitemap_urls': len(self.sitemap_urls),
                'success_rate': len(self.crawled_content) / len(self.sitemap_urls) * 100 if self.sitemap_urls else 0,
                'crawler_config': {
                    'delay': self.delay,
                    'max_workers': self.max_workers,
                    'max_pages': self.max_pages,
                    'min_content_length': self.min_content_length
                }
            },
            'pages': [asdict(content) for content in self.crawled_content]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"JSON檔案已儲存: {filepath}")
        return str(filepath)
    
    def save_to_markdown(self, filename: str = None) -> str:
        """儲存為Markdown格式"""
        if not filename:
            filename = f"sitemap_crawled_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# 網站爬取報告 - Sitemap版本\n\n")
            f.write(f"**基礎URL:** {self.base_url}\n")
            f.write(f"**爬取時間:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**總頁面數:** {len(self.crawled_content)}\n")
            f.write(f"**Sitemap URL數:** {len(self.sitemap_urls)}\n")
            
            if self.sitemap_urls:
                success_rate = len(self.crawled_content) / len(self.sitemap_urls) * 100
                f.write(f"**成功率:** {success_rate:.1f}%\n\n")
            
            # 按優先級統計
            priority_stats = defaultdict(int)
            for content in self.crawled_content:
                priority = content.sitemap_priority or 0.5
                priority_range = f"{priority:.1f}"
                priority_stats[priority_range] += 1
            
            if priority_stats:
                f.write("## 優先級分布\n\n")
                for priority in sorted(priority_stats.keys(), reverse=True):
                    f.write(f"- **優先級 {priority}:** {priority_stats[priority]} 頁面\n")
                f.write("\n")
            
            f.write("---\n\n")
            
            for i, content in enumerate(self.crawled_content, 1):
                f.write(f"## 頁面 {i}: {content.title}\n\n")
                f.write(f"**URL:** {content.url}\n")
                f.write(f"**字數:** {content.word_count}\n")
                f.write(f"**Sitemap優先級:** {content.sitemap_priority or 'N/A'}\n")
                f.write(f"**最後修改:** {content.sitemap_lastmod or 'N/A'}\n")
                f.write(f"**變更頻率:** {content.sitemap_changefreq or 'N/A'}\n")
                f.write(f"**爬取時間:** {content.timestamp}\n\n")
                
                if content.headers:
                    f.write("### 標題結構\n")
                    for header_level, headers in content.headers.items():
                        for header in headers:
                            f.write(f"- **{header_level.upper()}:** {header}\n")
                    f.write("\n")
                
                f.write("### 內容\n")
                display_content = content.content[:2000]
                if len(content.content) > 2000:
                    display_content += "...\n\n[內容已截斷]"
                f.write(f"{display_content}\n\n")
                
                f.write("---\n\n")
        
        self.logger.info(f"Markdown檔案已儲存: {filepath}")
        return str(filepath)
    
    def generate_rag_chunks(self, chunk_size: int = 1000, overlap: int = 200) -> List[Dict]:
        """生成適合RAG的文字塊"""
        chunks = []
        
        for content in self.crawled_content:
            text = content.content
            words = text.split()
            
            if len(words) <= chunk_size:
                chunks.append({
                    'chunk_id': f"{content.content_hash}_0",
                    'source_url': content.url,
                    'title': content.title,
                    'content': text,
                    'word_count': len(words),
                    'metadata': content.metadata,
                    'sitemap_priority': content.sitemap_priority,
                    'sitemap_lastmod': content.sitemap_lastmod,
                    'timestamp': content.timestamp,
                    'chunk_index': 0
                })
            else:
                chunk_index = 0
                for i in range(0, len(words), chunk_size - overlap):
                    chunk_words = words[i:i + chunk_size]
                    chunk_text = ' '.join(chunk_words)
                    
                    chunks.append({
                        'chunk_id': f"{content.content_hash}_{chunk_index}",
                        'source_url': content.url,
                        'title': content.title,
                        'content': chunk_text,
                        'word_count': len(chunk_words),
                        'metadata': content.metadata,
                        'sitemap_priority': content.sitemap_priority,
                        'sitemap_lastmod': content.sitemap_lastmod,
                        'timestamp': content.timestamp,
                        'chunk_index': chunk_index
                    })
                    chunk_index += 1
        
        return chunks
    
    def save_rag_chunks(self, chunk_size: int = 1000, overlap: int = 200, filename: str = None) -> str:
        """儲存RAG文字塊"""
        if not filename:
            filename = f"sitemap_rag_chunks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.output_dir / filename
        
        chunks = self.generate_rag_chunks(chunk_size, overlap)
        
        data = {
            'metadata': {
                'base_url': self.base_url,
                'total_chunks': len(chunks),
                'total_pages': len(self.crawled_content),
                'chunk_size': chunk_size,
                'overlap': overlap,
                'created_at': datetime.now().isoformat()
            },
            'chunks': chunks
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Sitemap RAG chunks已儲存: {filepath}, 共 {len(chunks)} 個塊")
        return str(filepath)


def main():
    """主程式"""
    parser = argparse.ArgumentParser(description='Sitemap爬蟲 - 生成RAG資料庫')
    parser.add_argument('url', help='要爬取的網站URL')
    parser.add_argument('--sitemap-url', help='指定的sitemap URL，如果提供則直接使用此sitemap')
    parser.add_argument('--delay', type=float, default=1.0, help='請求間隔秒數 (預設: 1.0)')
    parser.add_argument('--workers', type=int, default=5, help='並發執行緒數 (預設: 5)')
    parser.add_argument('--max-pages', type=int, default=500, help='最大爬取頁面數 (預設: 500)')
    parser.add_argument('--output', default='crawled_data', help='輸出目錄 (預設: crawled_data)')
    parser.add_argument('--no-robots', action='store_true', help='忽略robots.txt')
    parser.add_argument('--min-content', type=int, default=100, help='最小內容長度 (預設: 100)')
    parser.add_argument('--chunk-size', type=int, default=1000, help='RAG塊大小 (預設: 1000)')
    parser.add_argument('--overlap', type=int, default=200, help='RAG塊重疊大小 (預設: 200)')
    
    args = parser.parse_args()
    
    # 建立爬蟲
    crawler = SitemapCrawler(
        base_url=args.url,
        sitemap_url=args.sitemap_url,
        delay=args.delay,
        max_workers=args.workers,
        max_pages=args.max_pages,
        respect_robots=not args.no_robots,
        output_dir=args.output,
        min_content_length=args.min_content
    )
    
    try:
        # 開始爬取
        content = crawler.crawl()
        
        if content:
            print(f"\n爬取完成！")
            print(f"共爬取 {len(content)} 個頁面")
            
            # 顯示統計
            priority_counts = defaultdict(int)
            for c in content:
                priority = c.sitemap_priority or 0.5
                priority_counts[f"{priority:.1f}"] += 1
            
            if priority_counts:
                print("優先級分布:")
                for priority in sorted(priority_counts.keys(), reverse=True):
                    print(f"  優先級 {priority}: {priority_counts[priority]} 頁面")
            
            # 儲存各種格式
            json_file = crawler.save_to_json()
            md_file = crawler.save_to_markdown()
            rag_file = crawler.save_rag_chunks(args.chunk_size, args.overlap)
            
            print(f"\n檔案已儲存至: {args.output}")
            print(f"- JSON格式: {json_file}")
            print(f"- Markdown格式: {md_file}")
            print(f"- RAG塊格式: {rag_file}")
        else:
            print("未能爬取到任何內容")
            
    except KeyboardInterrupt:
        print("\n爬取被用戶中斷")
    except Exception as e:
        print(f"爬取過程中發生錯誤: {e}")


if __name__ == "__main__":
    main()
