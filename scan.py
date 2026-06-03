import subprocess
import json
import anthropic
import threading
import os
import argparse
import sys
from datetime import datetime
from urllib.parse import urlparse
import time
import xmltodict
import subprocess

# Claude API 初始化
# client = anthropic.Anthropic(api_key="")  # <- 請替換

class ReconScanner:
    def __init__(self, target):
        self.target = target
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results_dir = f"scan_results_{self.timestamp}"
        os.makedirs(self.results_dir, exist_ok=True)

        self.summary = ""

    def run_command(self, tool_name, command, timeout=300):
        print(f"[INFO] 執行 {tool_name}...")

        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            output = result.stdout + "\n" + result.stderr
            print(output)
            self.summary = self.summary + output
            return output
        
        except subprocess.TimeoutExpired:
            print(f"[WARNING] {tool_name} 執行超時")
            return ""
        except FileNotFoundError:
            print(f"[WARNING] {tool_name} 工具未找到，跳過此掃描")
            return ""
        except Exception as e:
            print(f"[WARNING] {tool_name} 發生錯誤: {e}")
            return ""

    def rustscan(self):
        # First run rustscan for fast port discovery
        rustscan_output = self.run_command("rustscan", f"rustscan -a {self.target} --range 1-65535")
        
        # Extract open ports from rustscan output
        open_ports = []
        for line in rustscan_output.split('\n'):
            if 'Open' in line and self.target in line:
                try:
                    port = line.split(':')[1].strip()
                    open_ports.append(port)
                except:
                    continue
        
        if open_ports:
            ports_str = ','.join(open_ports)
            print(f"[INFO] Found open ports: {ports_str}")
            # Run nmap on discovered ports
            self.run_command("nmap", f"nmap -Pn -p {ports_str} -sC -sV -oX {self.results_dir}/rustscan.xml {self.target}")
        else:
            print("[INFO] No open ports found by rustscan")
            
        output_json = os.path.join(self.results_dir, "rustscan_output.json")
        xml_path = f"{self.results_dir}/rustscan.xml"
        
        if os.path.exists(xml_path):
            with open(xml_path) as f:
                xml_data = f.read()

            parsed = xmltodict.parse(xml_data)
            json_data = json.dumps(parsed, indent=2)

            with open(output_json, 'w', encoding='utf-8') as f:
                f.write(json_data)
        else:
            print(f"[WARNING] XML file not found: {xml_path}")
            # Create empty JSON structure
            empty_data = {"nmaprun": {"host": {"ports": {"port": []}}}}
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(empty_data, f, indent=2)
        return

    def dirsearch(self, port=80, wordlist=None):
        print("[INFO] 執行 dirsearch...")
        
        # 檢查 dirsearch 是否存在
        try:
            subprocess.run(["which", "dirsearch"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("[WARNING] dirsearch 工具未找到，跳過目錄掃描")
            return
            
        if not wordlist:
            print("[WARNING] 未指定字典文件，跳過 dirsearch")
            return
            
        if not os.path.exists(wordlist):
            print(f"[WARNING] 字典文件不存在: {wordlist}，跳過 dirsearch")
            return

        output_json = os.path.join(self.results_dir, "dirsearch_output.json")
        cmd = [
            "dirsearch",
            "-u", f"http://{self.target}:{port}",  # 改用 https
            "-w", wordlist,
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            results = []
            def on_timeout():
                try:
                    proc.terminate()
                except:
                    pass
            timer = threading.Timer(3 * 60, on_timeout)
            timer.start()        
        
            for line in proc.stdout:
                if " 200 " in line or " 301 " in line:
                    if " 301 " in line:
                        line = line.split(" 301 ")[1]
                        print(line)
                        obj = {
                            "content-length": line.split()[1],
                            "redirect": line.split()[5],
                            "status": "301",
                            "url": f"http://{self.target}:{port}{line.split()[3]}"
                        }
                        print(obj)
                        self.whatweb(obj['redirect'])
                    else:
                        line = line.split(" 200 ")[1]
                        obj = {
                            "content-length": line.split()[1],
                            "redirect": "",
                            "status": "200",
                            "url": f"http://{self.target}:{port}{line.split()[3]}"
                        }
                        print(obj)
                        self.whatweb(obj['url'])
                    results.append(obj)

            proc.wait()
            timer.cancel()

            with open(output_json, "w") as f:
                json.dump(results, f, indent=4)
                
        except Exception as e:
            print(f"[WARNING] dirsearch 啟動失敗: {e}")
        return

    def whatweb(self, url):
        try:
            # 檢查 whatweb 是否存在
            subprocess.run(["which", "whatweb"], check=True, capture_output=True)
            self.run_command("whatweb", f"whatweb {url} --log-json={self.results_dir}/whatweb_output.json")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("[WARNING] whatweb 工具未找到，跳過 web 指紋掃描")
        except Exception as e:
            print(f"[WARNING] whatweb 執行失敗: {e}")
        return 
    
    def full_scan(self):
        print(f"[+] 開始掃描 {self.target}")
        print(f"[INFO] 所有掃描結果將儲存在: {self.results_dir}")
        
        # 執行基礎掃描
        try:
            self.rustscan()
        except Exception as e:
            print(f"[ERROR] 基礎掃描失敗: {e}")
            return self.summary

        # 嘗試解析掃描結果
        service_ports = {}
        try:
            with open(f"{self.results_dir}/rustscan_output.json", 'r') as f:
                rustscan_json = json.load(f)

            ports_obj = (
                rustscan_json
                .get("nmaprun", {})
                .get("host", {})
                .get("ports", {})
                .get("port", [])
            )
            
            # Handle different port data structures
            if isinstance(ports_obj, list):
                for p in ports_obj:
                    if isinstance(p, dict):
                        svc = p.get("service", {})
                        name = svc.get("@name", "") if isinstance(svc, dict) else ""
                        try:
                            portid = int(p.get("@portid"))
                            service_ports[name] = portid
                        except (ValueError, TypeError):
                            continue
            elif isinstance(ports_obj, dict):
                # Single port case
                svc = ports_obj.get("service", {})
                name = svc.get("@name", "") if isinstance(svc, dict) else ""
                try:
                    portid = int(ports_obj.get("@portid"))
                    service_ports[name] = portid
                except (ValueError, TypeError):
                    pass
                    
        except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
            print(f"[WARNING] 解析掃描結果失敗: {e}")
            
        print(f"[INFO] 發現服務端口: {service_ports}")
        
        # 並行執行各種掃描
        threads = []
        
        # Web 服務掃描
        web_ports = []
        for service_name, port in service_ports.items():
            if service_name in ["http", "https", "ssl/http"] or port in [80, 443, 8080, 8443]:
                web_ports.append(port)
                
        # 為每個 web 端口創建掃描線程
        for port in web_ports:
            protocol = "https" if port == 443 else "http"
            
            # dirsearch 線程
            wordlist = "wordlists/medium.txt"
            thread = threading.Thread(
                target=self.safe_run_scan, 
                args=("dirsearch", self.dirsearch, port, wordlist)
            )
            threads.append(thread)
            
            # whatweb 線程
            thread = threading.Thread(
                target=self.safe_run_scan,
                args=("whatweb", self.whatweb, f"{protocol}://{self.target}:{port}")
            )
            threads.append(thread)
        
        # 啟動所有線程
        print(f"[INFO] 啟動 {len(threads)} 個並行掃描任務")
        for t in threads:
            t.daemon = True  # 設為守護線程
            t.start()
        
        # 等待所有線程完成，但有超時機制
        for t in threads:
            t.join(timeout=600)  # 每個線程最多等待10分鐘
            if t.is_alive():
                print(f"[WARNING] 掃描線程超時，繼續執行其他任務")

        print(f"[+] 掃描完成")
        return self.summary
        
    def safe_run_scan(self, scan_name, scan_func, *args):
        """安全地運行掃描函數，捕獲所有異常"""
        try:
            print(f"[INFO] 開始 {scan_name} 掃描")
            scan_func(*args)
            print(f"[INFO] {scan_name} 掃描完成")
        except Exception as e:
            priscan_funcnt(f"[WARNING] {scan_name} 掃描失敗: {e}")
        return

def main():
    parser = argparse.ArgumentParser(description="自動化偵察與AI攻擊建議工具")
    parser.add_argument("target", help="目標 IP 或 URL")
    parser.add_argument("--lhost", default="10.0.0.1", help="你的攻擊機器 IP")
    args = parser.parse_args()

    scanner = ReconScanner(args.target)
    summary = scanner.full_scan()

if __name__ == "__main__":
    main()
