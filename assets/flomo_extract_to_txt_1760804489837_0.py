from bs4 import BeautifulSoup
import sys
import os
import glob

def extract_memo_contents(html_file_path):
    """从单个 HTML 文件中提取 class="content" 的 div 文本（保留段落换行）。"""
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    content_divs = soup.find_all('div', class_='content')
    memo_contents = []
    for div in content_divs:
        text = div.get_text(separator='\n', strip=True)
        if text:
            memo_contents.append(text)
    return memo_contents

def find_flomo_html_files(base_dir=None):
    # 查找指定目录（默认脚本自身所在目录）下的所有 .html 文件
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    pattern = os.path.join(base_dir, '*.html')
    return sorted(glob.glob(pattern), key=str.lower)

def main():
    # 将输出也放到脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(script_dir, "flomo导出.txt")

    html_files = find_flomo_html_files(script_dir)
    if not html_files:
        print("当前目录中未找到任何 .html 文件。")
        return

    total = 0
    first_file = True
    with open(out_path, 'w', encoding='utf-8') as out:
        for hf in html_files:
            try:
                notes = extract_memo_contents(hf)
            except Exception as e:
                print(f"解析 {hf} 时出错: {e}")
                continue
            if not notes:
                continue
            # 仅在不是第一个文件时写入分隔头
            if not first_file:
                out.write(f"--- {os.path.basename(hf)} ---\n")
            else:
                first_file = False

            for n in notes:
                out.write(n + "\n")
                total += 1

    print(f"已处理 {len(html_files)} 个 HTML 文件，提取 {total} 条笔记到 {out_path}")

if __name__ == "__main__":
    main()