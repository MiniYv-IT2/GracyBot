#!/usr/bin/env python3
"""使用 Python tokenize 精确去除注释和 docstring"""
import tokenize
import io
import sys

def strip_all(source: str) -> str:
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    
    # 收集每个 token 的删除范围，按行号索引
    # deletes[line_no] = [(col_start, col_end), ...]
    deletes = {}

    for i, tok in enumerate(tokens):
        tok_type = tok.type
        tok_str = tok.string
        sline, scol = tok.start
        eline, ecol = tok.end

        # ── # 注释 ──
        if tok_type == tokenize.COMMENT:
            for ln in range(sline, eline + 1):
                if ln not in deletes:
                    deletes[ln] = []
                start = scol if ln == sline else 0
                deletes[ln].append((start, None))  # None = 到行尾
            continue

        # ── """ docstring（仅在独立位置） ──
        if tok_type == tokenize.STRING and tok_str.startswith(('"""', "'''")):
            prev = tokens[i-1] if i > 0 else None
            prev_type = prev.type if prev else tokenize.NEWLINE
            if prev_type in (tokenize.INDENT, tokenize.NEWLINE, tokenize.NL, tokenize.DEDENT):
                for ln in range(sline, eline + 1):
                    if ln not in deletes:
                        deletes[ln] = []
                    start = scol if ln == sline else 0
                    deletes[ln].append((start, None))  # None = 到行尾
            continue

    if not deletes:
        return source

    # 按行处理
    source_lines = source.split('\n')
    result_lines = []

    for ln, line in enumerate(source_lines, 1):
        if ln not in deletes:
            result_lines.append(line)
            continue

        ranges = []
        for start, end in deletes[ln]:
            if end is None:
                end = len(line)
            ranges.append((start, end))

        # 合并重叠范围
        ranges.sort()
        merged = []
        for r in ranges:
            if merged and r[0] <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], r[1]))
            else:
                merged.append(r)

        # 用空格替换删除范围
        chars = list(line)
        for start, end in merged:
            for pos in range(start, min(end, len(chars))):
                chars[pos] = ' '

        result_lines.append(''.join(chars).rstrip())

    return '\n'.join(result_lines)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('output', nargs='?')
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8-sig') as f:
        source = f.read()

    result = strip_all(source)

    # 验证语法
    try:
        compile(result, args.input, 'exec')
    except SyntaxError as e:
        print(f"❌ 语法错误: {e}", file=sys.stderr)
        lines = result.split('\n')
        if e.lineno and e.lineno <= len(lines):
            ctx_start = max(0, e.lineno - 3)
            ctx_end = min(len(lines), e.lineno + 2)
            for ln in range(ctx_start, ctx_end):
                marker = '→' if ln + 1 == e.lineno else ' '
                print(f"{marker} {ln+1}: {lines[ln]}")
        sys.exit(1)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"✅ 已写入 {args.output}")
    else:
        print(result)


if __name__ == '__main__':
    main()
