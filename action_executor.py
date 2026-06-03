import subprocess
import shlex
import os
import pty
import sys

def execute_action(action_plan: dict, target_ip: str) -> tuple[str, str]:
    """
    解析並執行由 LLM 產生的行動計畫。
    *** 修正：現在會回傳 stdout 和 stderr ***
    """
    command_str = action_plan.get("command")
    tool = action_plan.get("tool")

    if not command_str:
        print("[!] 行動計畫中未找到可執行的 'command'。")
        return "", "No command found in action plan."

    # 替換 [TARGET_IP] 占位符
    command_str = command_str.replace("[TARGET_IP]", target_ip)

    print(f"\n[+] 準備執行工具 '{tool}'...")
    print(f"    - 目標 IP: {target_ip}")
    print(f"    - 指令: {command_str}")

    # 檢測是否為互動式命令
    interactive_tools = ['msfconsole', 'sqlmap', 'ncat', 'nc', 'telnet', 'ssh']
    is_interactive = any(cmd in command_str for cmd in interactive_tools)
    
    if is_interactive:
        return execute_interactive_action(command_str, tool)

    try:
        args = shlex.split(command_str)
        
        print("\n" + "="*20 + " 指令執行開始 " + "="*20)
        print("[+] 實時輸出:")
        
        # 使用 Popen 來實時顯示輸出
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 將 stderr 合併到 stdout
            text=True,
            encoding='utf-8',
            bufsize=1,
            universal_newlines=True
        )
        
        stdout_lines = []
        # 實時讀取並顯示輸出
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip())  # 實時顯示
                stdout_lines.append(output)
        
        # 等待進程完成
        return_code = process.wait()
        full_stdout = ''.join(stdout_lines)
        
        print("\n" + "="*20 + " 指令執行完成 " + "="*20)
        
        if return_code == 0:
            print("[✅] 指令成功執行。")
        else:
            print(f"[⚠️] 指令執行失敗，返回碼: {return_code}")
            
        print("="*54)
        return full_stdout, ""

    except FileNotFoundError:
        error_msg = f"錯誤：找不到指令或工具 '{args[0]}'。"
        print(f"[!] {error_msg}")
        return "", error_msg
    except subprocess.TimeoutExpired:
        error_msg = "錯誤：指令執行超時。"
        print(f"[!] {error_msg}")
        return "", error_msg
    except Exception as e:
        error_msg = f"執行指令時發生未預期的錯誤: {e}"
        print(f"[!] {error_msg}")
        return "", error_msg

def execute_interactive_action(command_str: str, tool: str) -> tuple[str, str]:
    """
    執行需要互動的命令 (如 msfconsole)
    """
    print(f"\n[🎯] 檢測到互動式工具 '{tool}'")
    print("=" * 60)
    print("🔥 正在啟動互動模式！")
    print("💡 提示：")
    print("   - 如果是 msfconsole，攻擊成功後可以使用 'sessions -l' 查看會話")
    print("   - 使用 'sessions -i 1' 進入第一個會話")
    print("   - 在 meterpreter 中可以使用: sysinfo, getuid, shell 等命令")
    print("   - 按 Ctrl+C 退出互動模式")
    print("=" * 60)
    
    try:
        args = shlex.split(command_str)
        
        # 使用 os.system 來直接執行命令，保持完整的終端互動
        print(f"[+] 執行: {command_str}")
        result = os.system(command_str)
        
        if result == 0:
            print("\n[✅] 互動式會話已結束")
            return "Interactive session completed successfully", ""
        else:
            print(f"\n[⚠️] 互動式會話結束，返回碼: {result}")
            return f"Interactive session ended with code {result}", ""
            
    except KeyboardInterrupt:
        print("\n[!] 使用者中斷了互動式會話")
        return "User interrupted interactive session", ""
    except Exception as e:
        error_msg = f"執行互動式命令時發生錯誤: {e}"
        print(f"[!] {error_msg}")
        return "", error_msg
