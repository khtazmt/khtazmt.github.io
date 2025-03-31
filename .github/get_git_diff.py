import subprocess
import sys
import os
from datetime import datetime, timedelta
import re
from urllib.parse import unquote

def get_git_diff(commit_range=None):
    """
    获取git diff的内容
    
    Args:
        commit_range: 可选的提交范围，例如 'HEAD^..HEAD'
    
    Returns:
        str: git diff的输出内容
    """
    try:
        if commit_range:
            cmd = ['git', 'diff', commit_range]
        else:
            # 默认获取前一天到现在的改动
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            today = datetime.now().strftime('%Y-%m-%d')
            # 使用 --since 和 --until 来指定时间范围
            cmd = ['git', 'log', '-p', f'--since={yesterday} 00:00:00', f'--until={today} 23:59:59']
            
        # 设置环境变量以确保 git 输出使用 UTF-8 编码
        env = os.environ.copy()
        env['LANG'] = 'en_US.UTF-8'
        env['GIT_TERMINAL_PROMPT'] = '0'
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding='utf-8',  # 明确指定编码为 UTF-8
            errors='replace',  # 处理无法解码的字符
            env=env,
            check=True
        )
        
        return result.stdout
        
    except subprocess.CalledProcessError as e:
        print(f"获取git diff时发生错误: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"发生未知错误: {e}", file=sys.stderr)
        return None

def get_indent_level(line):
    """获取内容的缩进层级"""
    # 移除前面的 "- " 或 "+ "
    content = re.sub(r'^[+-] ', '', line.strip())
    
    # 检查原始行的缩进
    original_indent = len(line) - len(line.lstrip())
    base_level = original_indent // 2  # 每两个空格算一级
    
    # 检查内容中的额外缩进
    if content.startswith('- '):
        content = content[2:]
        content_indent = len(content) - len(content.lstrip())
        return base_level + (content_indent // 2) + 1
    
    return base_level + 1

def format_content_with_indent(content_list):
    """格式化内容，添加正确的 logseq 缩进"""
    formatted = []
    addition_block = []
    
    # 构建层级结构
    hierarchy = []
    for line in content_list:
        if not line:  # 空行
            hierarchy.append((line, 0))
            continue
            
        if line.startswith('- [[') or line.startswith('- 20'):  # 标题行
            hierarchy.append((line, 0))
            continue
        
        # 计算缩进级别
        indent_match = re.match(r'^(\t+)- ', line)
        if indent_match:
            # 使用制表符数量确定级别
            level = len(indent_match.group(1))
            content = line.strip()
            hierarchy.append((content, level))
        else:
            # 没有缩进，默认为一级
            content = line.strip()
            hierarchy.append((content, 1))
    
    # 根据层级结构生成输出
    previous_level = 0
    for content, level in hierarchy:
        if not content:  # 保留空行
            if addition_block:
                formatted.extend(addition_block)
                formatted.append('')
                addition_block = []
            formatted.append(content)
            continue
            
        # 处理标题行
        if content.startswith('- [[') or content.startswith('- 20'):
            if addition_block:
                formatted.extend(addition_block)
                formatted.append('')
                addition_block = []
            formatted.append(content)
            previous_level = 0
            continue
            
        # 跳过转移内容的标记行
        if content.strip().startswith('从 '):
            continue
            
        # 处理普通内容行
        if content.strip():
            # 使用制表符生成缩进
            indent = '\t' * level
            
            # 确保行以 "- " 开头
            if not content.startswith('- '):
                content = '- ' + content
            
            # 只处理添加的内容或普通内容
            if '**' in content:
                content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
                addition_block.append(indent + content)
            elif '~~' not in content:
                formatted.append(indent + content)
                previous_level = level
    
    # 处理最后的添加块
    if addition_block:
        formatted.extend(addition_block)
    
    return formatted

def normalize_content(content):
    """标准化内容，移除缩进、换行、链接和多余空格"""
    # 移除 markdown 列表符号和缩进
    content = re.sub(r'^[\s-]*', '', content)
    
    # 保留 logseq 特定格式的内容
    def preserve_logseq_format(match):
        return f" {match.group(0)} "  # 在特殊格式前后添加空格
    
    # 处理 logseq 特殊格式
    content = re.sub(r'\(\([^)]+\)\)', preserve_logseq_format, content)  # 引用格式 ((id))
    content = re.sub(r'\[\[[^\]]+\]\]', preserve_logseq_format, content)  # 页面链接 [[page]]
    content = re.sub(r'TODO|DOING|DONE|NOW|LATER|WAITING|CANCELED', preserve_logseq_format, content)  # 任务状态
    
    # 移除 markdown 链接格式 [text](url)，但保留文本
    content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)
    
    # 移除 HTML 链接
    content = re.sub(r'<[^>]+>', '', content)
    
    # 规范化空白字符
    content = ' '.join(content.split())
    return content

def has_real_content(content_list, ignore_patterns):
    """检查是否有实际内容（不包括标题、空行和结构变化）"""
    if len(content_list) <= 1:  # 只有标题或空
        return False
    
    has_meaningful_change = False
    previous_content = None
    deletion_count = 0
    
    for line in content_list[1:]:  # 跳过标题
        if line and not line.isspace() and not line.startswith('从 '):
            content = line.strip('- ').strip()
            if content and not any(pattern in content for pattern in ignore_patterns):
                # 标准化当前内容
                normalized = normalize_content(content)
                if not normalized:  # 如果标准化后为空，说明只有格式没有实际内容
                    continue
                
                # 检查是否是删除内容
                if '~~' in content and '**' not in content:
                    deletion_count += 1
                    if deletion_count > 3:  # 如果连续删除超过3行，忽略这个文件
                        return False
                else:
                    deletion_count = 0
                
                # 检查是否只是结构变化
                if '~~' in content or '**' in content:
                    clean_content = re.sub(r'~~.*?~~|\*\*.*?\*\*', '', content)
                    normalized_clean = normalize_content(clean_content)
                    if normalized_clean and (previous_content is None or normalized_clean != previous_content):
                        has_meaningful_change = True
                else:
                    if previous_content is None or normalized != previous_content:
                        has_meaningful_change = True
                
                previous_content = normalized
    
    return has_meaningful_change

def add_spaces_around_refs(content):
    """在引用格式前后添加空格"""
    # 使用正则表达式查找所有引用格式
    pattern = r'\(\([^)]+\)\)'
    parts = []
    last_end = 0
    
    for match in re.finditer(pattern, content):
        start, end = match.span()
        # 添加前面的文本
        prefix = content[last_end:start].rstrip()
        parts.append(prefix)
        # 添加带空格的引用
        ref = match.group()
        if parts and not parts[-1].endswith(' '):  # 检查列表是否为空
            parts[-1] += ' '
        parts.append(ref)
        last_end = end
    
    # 添加剩余的文本
    if last_end < len(content):
        remaining = content[last_end:].lstrip()
        if remaining:
            if parts and not parts[-1].endswith(' '):  # 检查列表是否为空
                parts.append(' ')
            parts.append(remaining)
    
    # 如果列表为空，直接返回原内容
    return ''.join(parts) if parts else content

def format_diff_line(old_line, new_line):
    """格式化差异行，使用Markdown语法标记变化"""
    # 如果内容完全相同，返回None
    if old_line == new_line:
        return None
    
    # 去掉行首的 '- ' 或 '+ ' 并处理可能的多余空格
    old_content = old_line[2:].strip()
    new_content = new_line[2:].strip()
    
    # 去掉可能存在的额外 '- ' 前缀
    if old_content.startswith('- '):
        old_content = old_content[2:].strip()
    if new_content.startswith('- '):
        new_content = new_content[2:].strip()
    
    # 在引用格式前后添加空格
    old_content = add_spaces_around_refs(old_content)
    new_content = add_spaces_around_refs(new_content)
    
    # 标准化并比较内容
    old_normalized = normalize_content(old_content)
    new_normalized = normalize_content(new_content)
    if old_normalized == new_normalized:
        return None
    
    # 分别返回删除和添加的内容
    return {
        'deleted': f"- ~~{old_content}~~",
        'added': f"- **{new_content}**"
    }

def save_diff_to_file(diff_content, output_dir="diffs"):
    """
    将diff内容保存到文件
    
    Args:
        diff_content: diff的内容
        output_dir: 输出目录，默认为'diffs'
    
    Returns:
        str: 保存的文件路径
    """
    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        filename = "最近一天的新增.md"
        filepath = os.path.join(output_dir, filename)
        
        # 需要忽略的格式
        ignore_patterns = [
            'id::',
            'collapsed::',
            'created::',
            'updated::',
        ]
        
        # 使用字典来存储每个标题的原始内容行
        title_raw_contents = {}
        current_title = None
        current_content = []
        source_title = None
        deleted_content = None  # 初始化 deleted_content
        is_new_file = False
        new_file_line_count = 0  # 新增文件的行数计数器
        last_was_addition = False  # 初始化 last_was_addition
        
        for line in diff_content.splitlines():
            if line.startswith('diff --git'):
                # 处理前一个文件的内容
                if current_content and current_title:
                    if has_real_content(current_content, ignore_patterns):
                        # 将原始内容行添加到对应标题的列表中
                        if current_title not in title_raw_contents:
                            title_raw_contents[current_title] = []
                        title_raw_contents[current_title].extend(current_content[1:])  # 跳过标题行
                
                current_content = []
                is_new_file = False
                
                # 提取并处理文件名
                match = re.search(r'b/(.+)$', line)
                if match:
                    file_path = match.group(1)
                    
                    # 处理文件路径
                    # 1. 处理八进制编码的中文字符
                    if '\\' in file_path:
                        try:
                            # 提取八进制编码部分（排除.md"等后缀）
                            encoded_parts = re.findall(r'\\([0-7]{3})', file_path)
                            if encoded_parts:
                                # 将八进制转换为字节序列
                                bytes_array = bytes([int(x, 8) for x in encoded_parts])
                                # 将字节序列解码为UTF-8字符串
                                decoded = bytes_array.decode('utf-8')
                                # 替换原文件名中的八进制部分
                                file_path = re.sub(r'\\[0-7]{3}', lambda _: decoded[len(re.findall(r'\\[0-7]{3}', file_path[:_.start()])):len(re.findall(r'\\[0-7]{3}', file_path[:_.end()]))], file_path)
                        except Exception as e:
                            print(f"解码文件名失败: {e}", file=sys.stderr)
                            # 解码失败时保持原样
                            pass
                    elif '%' in file_path:
                        try:
                            file_path = unquote(file_path)
                        except:
                            pass
                    
                    # 2. 移除常见前缀
                    title = file_path.replace('pages/', '').replace('journals/', '')
                    # 3. 移除文件扩展名
                    title = re.sub(r'\.md"?$', '', title)
                    # 4. 移除日期格式中的下划线
                    title = re.sub(r'(\d{4})_(\d{2})_(\d{2})', r'\1\2\3', title)
                    
                    if title:
                        current_content.append(f"- {title}")
                        current_title = title
            
            elif line.startswith('+++ b/'):
                is_new_file = True
            
            elif line.startswith(('+', '-')) and not line.startswith(('+++ ', '--- ')):
                content = line.strip()
                
                if not any(pattern in content for pattern in ignore_patterns) and len(content) > 1:
                    # 处理删除的内容
                    if content.startswith('-'):
                        if deleted_content is None:
                            deleted_content = content
                        source_title = current_title
                        last_was_addition = False
                    # 处理添加的内容
                    elif content.startswith('+'):
                        content_without_prefix = content[1:].strip()
                        if content_without_prefix.startswith('- '):
                            content_without_prefix = content_without_prefix[2:].strip()
                        current_content.append('- ' + content_without_prefix)
                        deleted_content = None
                        last_was_addition = True
        
        # 处理最后一个文件的内容
        if current_content and current_title and has_real_content(current_content, ignore_patterns):
            if current_title not in title_raw_contents:
                title_raw_contents[current_title] = []
            title_raw_contents[current_title].extend(current_content[1:])
        
        # 生成最终的内容
        content_files = []
        for title, raw_contents in title_raw_contents.items():
            if raw_contents:  # 只处理有内容的标题
                # 添加标题
                content_files.append(f"- {format_page_title(title)}")
                
                # 预处理：标准化内容并移除已有缩进
                standardized_contents = []
                for line in raw_contents:
                    if line.strip():
                        # 移除已有的缩进
                        content = line.strip()
                        if not content.startswith('- '):
                            content = '- ' + content
                        standardized_contents.append(content)
                
                # 检查是否有不连续的内容块
                blocks = []
                current_block = []
                for line in standardized_contents:
                    if line.strip():
                        current_block.append(line)
                    else:
                        if current_block:
                            blocks.append(current_block)
                            current_block = []
                
                if current_block:  # 添加最后一个块
                    blocks.append(current_block)
                
                # 分别处理每个块，保持独立性
                all_processed = []
                for block in blocks:
                    processed = analyze_hierarchy(block)
                    all_processed.extend(processed)
                    all_processed.append('')  # 块之间添加空行
                
                # 添加处理后的内容
                if all_processed:
                    content_files.extend(all_processed)
                    content_files.append('')  # 标题之间添加空行
        
        # 移除末尾的空行
        while content_files and not content_files[-1]:
            content_files.pop()
        
        # 只有在有实际内容时才写入文件
        if content_files:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content_files))
            return filepath
        return None
        
    except Exception as e:
        print(f"保存文件时发生错误: {e}", file=sys.stderr)
        return None

def format_page_title(title):
    """格式化页面标题，添加 [[]] 标记"""
    # 如果是日期格式，不添加 [[]]
    if re.match(r'^\d{8}$', title):
        return title
    # 如果已经有 [[]]，不重复添加
    if title.startswith('[[') and title.endswith(']]'):
        return title
    # 如果标题中已经包含 [[]] 格式的部分，不处理
    if '[[' in title or ']]' in title:
        return title
    return f"[[{title}]]"

def analyze_hierarchy(raw_contents):
    """分析内容的层级关系并添加正确的缩进"""
    processed = []
    
    # 简化处理：对于大多数内容，默认使用一级缩进
    # 只有明确识别为嵌套内容时才使用更深的缩进
    for line in raw_contents:
        if not line.strip():
            continue
            
        content = line.strip()
        # 确保行以 "- " 开头
        if not content.startswith('- '):
            content = '- ' + content
            
        # 跳过删除的内容
        if '~~' in content and '**' not in content:
            continue
            
        # 处理添加的内容
        if '**' in content:
            content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
        
        # 检查是否是引用内容，可能需要额外缩进
        is_quote = (content.startswith('- "') or content.startswith('- 「') or 
                   content.startswith('- #') or content.startswith('- (('))
        
        # 检查是否是链接内容
        is_link = ('http' in content or 'bilibili' in content or '哔哩哔哩' in content or 
                  content.startswith('- 🔗') or '[' in content and ']' in content)
        
        # 默认使用一级缩进
        level = 1
        
        # 特殊情况：引用内容和链接内容可能是子项
        if is_quote and len(processed) > 0 and processed[-1].startswith('\t- '):
            # 如果前一项是一级缩进，并且当前是引用，可能是子项
            prev_line = processed[-1].strip()
            if not (prev_line.startswith('- "') or prev_line.startswith('- 「') or 
                    prev_line.startswith('- #') or prev_line.startswith('- ((')):
                level = 2
        
        # 添加缩进并保存
        indent = '\t' * level
        processed.append(indent + content)
    
    return processed

if __name__ == "__main__":
    # 如果提供了命令行参数，则使用它作为commit范围
    commit_range = sys.argv[1] if len(sys.argv) > 1 else None
    
    diff_content = get_git_diff(commit_range)
    if diff_content:
        # 保存到文件
        output_file = save_diff_to_file(diff_content)
        if output_file:
            print(f"diff内容已保存到: {output_file}")
        else:
            sys.exit(1)
    else:
        sys.exit(1) 