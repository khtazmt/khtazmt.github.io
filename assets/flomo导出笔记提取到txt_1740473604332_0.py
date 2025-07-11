from bs4 import BeautifulSoup
import sys
import os
import glob

def extract_memo_contents(html_file_path):
    # 读取HTML文件
    with open(html_file_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    # 解析HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 找到所有具有"content"类的div
    content_divs = soup.find_all('div', class_='content')
    
    # 提取每个div中的文本内容并处理
    memo_contents = []
    for div in content_divs:
        # 获取div中的所有段落文本，保留段落间的换行
        paragraphs = div.find_all('p')
        # 使用换行符而不是空格连接段落
        combined_text = '\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        if combined_text:
            memo_contents.append(combined_text)
    
    return memo_contents

def find_flomo_html_file():
    # 查找当前目录下是否有flomo@开头的文件夹
    flomo_folders = glob.glob('flomo@*')
    
    # 如果没找到，尝试在特定路径查找
    if not flomo_folders:
        specific_path = "c:\\data"
        if os.path.exists(specific_path):
            flomo_folders = glob.glob(os.path.join(specific_path, 'flomo@*'))
    
    for folder in flomo_folders:
        # 查找文件夹中的HTML文件
        html_files = glob.glob(os.path.join(folder, '*.html'))
        if html_files:
            return html_files[0]  # 返回找到的第一个HTML文件
    
    # 如果还没找到，直接查找当前目录下的html文件
    html_files = glob.glob('*.html')
    if html_files:
        return html_files[0]
    
    return None

def main():
    # 如果提供了HTML文件路径作为参数，则使用该路径
    if len(sys.argv) >= 2:
        html_file_path = sys.argv[1]
    else:
        # 否则，自动查找flomo@开头的文件夹中的HTML文件
        html_file_path = find_flomo_html_file()
        if not html_file_path:
            print("未找到flomo笔记文件。请提供HTML文件路径：")
            print("Usage: python extract_flomo_notes.py <html_file_path> [output_file_path]")
            sys.exit(1)
        print(f"找到flomo笔记文件：{html_file_path}")
    
    memo_contents = extract_memo_contents(html_file_path)
    
    # 如果提供了输出文件路径，则使用该路径
    if len(sys.argv) >= 3:
        output_file_path = sys.argv[2]
    else:
        # 否则，输出到HTML文件所在的文件夹
        html_dir = os.path.dirname(os.path.abspath(html_file_path))
        if not html_dir:  # 如果HTML文件在当前目录
            html_dir = os.getcwd()
        output_file_path = os.path.join(html_dir, "flomo导出.txt")
    
    # 写入文件
    with open(output_file_path, 'w', encoding='utf-8') as file:
        for content in memo_contents:
            file.write(content + '\n')  # 每条笔记后添加一个换行
    
    print(f"已提取 {len(memo_contents)} 条笔记到 {output_file_path}")

if __name__ == "__main__":
    main() 