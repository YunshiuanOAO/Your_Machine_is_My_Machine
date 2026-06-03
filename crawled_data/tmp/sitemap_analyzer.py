#!/usr/bin/env python3
"""
Sitemap分析工具
用於檢查和分析網站的sitemap結構
"""

import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
import json
from datetime import datetime
from pathlib import Path
import argparse


class SitemapAnalyzer:
    """Sitemap分析器"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        parsed_url = urlparse(base_url)
        self.domain = parsed_url.netloc
        self.scheme = parsed_url.scheme
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; SitemapAnalyzer/1.0)'
        })
    
    def discover_sitemaps(self) -> dict:
        """發現所有sitemap文件"""
        result = {
            'found_sitemaps': [],
            'robots_sitemaps': [],
            'common_path_sitemaps': [],
            'total_urls': 0,
            'analysis_time': datetime.now().isoformat()
        }
        
        # 檢查robots.txt
        try:
            robots_url = f"{self.scheme}://{self.domain}/robots.txt"
            response = self.session.get(robots_url, timeout=10)
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        result['robots_sitemaps'].append(sitemap_url)
                        print(f"從robots.txt發現sitemap: {sitemap_url}")
        except Exception as e:
            print(f"無法讀取robots.txt: {e}")
        
        # 檢查常見位置
        common_paths = [
            '/sitemap.xml',
            '/sitemap_index.xml',
            '/sitemaps.xml',
            '/sitemap/sitemap.xml',
            '/sitemaps/sitemap.xml',
            '/sitemap/index.xml'
        ]
        
        for path in common_paths:
            sitemap_url = f"{self.scheme}://{self.domain}{path}"
            try:
                response = self.session.head(sitemap_url, timeout=10)
                if response.status_code == 200:
                    result['common_path_sitemaps'].append(sitemap_url)
                    print(f"發現sitemap: {sitemap_url}")
            except:
                continue
        
        # 合併所有發現的sitemap
        all_sitemaps = list(set(result['robots_sitemaps'] + result['common_path_sitemaps']))
        result['found_sitemaps'] = all_sitemaps
        
        return result
    
    def analyze_sitemap(self, sitemap_url: str) -> dict:
        """分析單個sitemap文件"""
        result = {
            'url': sitemap_url,
            'type': 'unknown',
            'urls': [],
            'sub_sitemaps': [],
            'total_urls': 0,
            'error': None
        }
        
        try:
            print(f"分析sitemap: {sitemap_url}")
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
                result['type'] = 'sitemap_index'
                print(f"  類型: Sitemap Index (包含 {len(sitemapindex_elements)} 個子sitemap)")
                
                for sitemap_elem in sitemapindex_elements:
                    loc_elem = sitemap_elem.find('{0}loc'.format(namespace))
                    if loc_elem is not None:
                        sub_sitemap_url = loc_elem.text.strip()
                        result['sub_sitemaps'].append(sub_sitemap_url)
                        
                        # 遞歸分析子sitemap
                        sub_result = self.analyze_sitemap(sub_sitemap_url)
                        result['total_urls'] += sub_result['total_urls']
            else:
                result['type'] = 'urlset'
                url_elements = root.findall('.//{0}url'.format(namespace))
                
                print(f"  類型: URL集合 (包含 {len(url_elements)} 個URL)")
                
                for url_elem in url_elements:
                    url_data = {}
                    
                    # 提取URL
                    loc_elem = url_elem.find('{0}loc'.format(namespace))
                    if loc_elem is not None:
                        url_data['url'] = loc_elem.text.strip()
                    else:
                        continue
                    
                    # 提取其他信息
                    priority_elem = url_elem.find('{0}priority'.format(namespace))
                    if priority_elem is not None:
                        try:
                            url_data['priority'] = float(priority_elem.text.strip())
                        except:
                            url_data['priority'] = None
                    
                    lastmod_elem = url_elem.find('{0}lastmod'.format(namespace))
                    if lastmod_elem is not None:
                        url_data['lastmod'] = lastmod_elem.text.strip()
                    
                    changefreq_elem = url_elem.find('{0}changefreq'.format(namespace))
                    if changefreq_elem is not None:
                        url_data['changefreq'] = changefreq_elem.text.strip()
                    
                    result['urls'].append(url_data)
                
                result['total_urls'] = len(result['urls'])
                
                # 顯示統計
                if result['urls']:
                    priorities = [url.get('priority') for url in result['urls'] if url.get('priority') is not None]
                    if priorities:
                        avg_priority = sum(priorities) / len(priorities)
                        print(f"    平均優先級: {avg_priority:.2f}")
                    
                    with_lastmod = len([url for url in result['urls'] if url.get('lastmod')])
                    print(f"    有最後修改時間的URL: {with_lastmod}/{len(result['urls'])}")
        
        except Exception as e:
            result['error'] = str(e)
            print(f"  錯誤: {e}")
        
        return result
    
    def full_analysis(self) -> dict:
        """完整分析網站的sitemap結構"""
        print(f"開始分析網站: {self.base_url}")
        print("=" * 50)
        
        # 發現sitemap
        discovery = self.discover_sitemaps()
        
        if not discovery['found_sitemaps']:
            print("未發現任何sitemap文件")
            return discovery
        
        # 分析每個sitemap
        detailed_analysis = []
        total_urls = 0
        
        for sitemap_url in discovery['found_sitemaps']:
            analysis = self.analyze_sitemap(sitemap_url)
            detailed_analysis.append(analysis)
            total_urls += analysis['total_urls']
        
        # 生成完整報告
        full_report = {
            'base_url': self.base_url,
            'discovery': discovery,
            'detailed_analysis': detailed_analysis,
            'summary': {
                'total_sitemaps': len(discovery['found_sitemaps']),
                'total_urls': total_urls,
                'analysis_time': datetime.now().isoformat()
            }
        }
        
        print("\n" + "=" * 50)
        print("分析總結:")
        print(f"發現的sitemap文件數: {len(discovery['found_sitemaps'])}")
        print(f"總URL數量: {total_urls}")
        
        return full_report
    
    def save_analysis(self, analysis: dict, filename: str = None) -> str:
        """保存分析結果"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"sitemap_analysis_{timestamp}.json"
        
        filepath = Path(filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        
        print(f"分析結果已保存到: {filepath}")
        return str(filepath)


def main():
    """主程式"""
    parser = argparse.ArgumentParser(description='Sitemap分析工具')
    parser.add_argument('url', help='要分析的網站URL')
    parser.add_argument('--output', help='輸出檔案名稱')
    
    args = parser.parse_args()
    
    try:
        analyzer = SitemapAnalyzer(args.url)
        analysis = analyzer.full_analysis()
        
        # 保存結果
        output_file = analyzer.save_analysis(analysis, args.output)
        
        print(f"\n分析完成！結果已保存到: {output_file}")
        
    except Exception as e:
        print(f"分析過程中發生錯誤: {e}")


if __name__ == "__main__":
    main()
