# -*- coding: utf-8 -*-
"""
================================================================================
 简易 Python 教学解释器（供"代码可视化编辑器"使用）
================================================================================

 【为什么自己写解释器，而不用 Python 的 exec()？】
     1. 安全   ：exec 会执行任意代码；这里只解析教学需要的少量语句。
     2. 可视化 ：exec 无法告诉我们"每一步执行后内存变成什么样"；
                 本解释器把代码"展开"成逐步执行记录，
                 每一步都保存完整内存快照，因此支持单步前进/后退回放。
     3. 可控   ：遇到不支持的语句给出友好中文报错，而不是崩溃。

 【支持的语法（对应高中《数据与计算》Python 基础教学）】
     变量赋值      a = 10 / b = a + 2 / s = "hi"
     列表          lst = [1, 2, 3]
     列表操作      lst.append(x) / lst.insert(i, x) / lst.pop() / lst.remove(x)
     索引操作      lst[0] = x / lst[i]
     for 循环      for i in lst: / for i in range(5):
     while 循环    while a < 5:
     if 分支       if a > 5: / elif / else
     输出          print(a)
     表达式        四则运算、比较、逻辑、len()、range()、字符串拼接等

 【核心设计：把代码"展开"成线性步骤】
     循环会被展开成若干次顺序执行的步骤（for 有几个元素就执行几次），
     分支只保留实际走到的路径。这样回放就是"平铺"的，
     天然支持 ← 回退上一步、→ 前进下一步。
     展开时用影子环境模拟执行，并做死循环保护（超过 MAX_LOOP 次报错）。
================================================================================
"""
import re
import copy

# 循环展开/迭代上限：防止学生写出死循环导致界面卡死
MAX_LOOP = 200


class CodeError(Exception):
    """代码解析或执行错误。message 会直接显示在界面上（中文友好提示）。"""
    pass


# ------------------------------------------------------------------------------
# 表达式求值（受限环境，安全白名单）
# ------------------------------------------------------------------------------
# 禁止出现在表达式中的敏感词（用单词边界匹配，避免误伤变量名）
_BLACKLIST = ("import", "open", "exec", "compile", "globals", "locals",
              "eval", "system", "input", "del")


def eval_expr(expr, env):
    """
    在"受限环境"中求值一个表达式，返回 Python 值。

    参数:
        expr: 表达式字符串，如 "a + b * 2"、"[1, 2, 3]"、"lst[0]"、"len(lst)"
        env : 变量环境字典，{变量名: 值}

    返回:
        表达式的值（int / float / str / bool / list）

    安全性设计:
        · eval 的 globals 传空 builtins → 表达式拿不到任何系统函数
        · 白名单函数：len / range / abs / min / max / sum / int / str / float
        · 黑名单单词检查：import、open、exec 等一律禁止
    """
    expr = expr.strip()
    if not expr:
        raise CodeError("表达式为空")

    # 双下划线访问（如 __import__、__class__）一律禁止
    if "__" in expr:
        raise CodeError("表达式包含不允许的内容：__")
    for word in _BLACKLIST:
        if re.search(r"\b" + word + r"\b", expr):
            raise CodeError(f"表达式包含不允许的内容：{word}")

    # 构造受限求值环境：先放白名单函数，再放用户变量（用户变量优先）
    safe_env = {
        "len": len, "range": range, "abs": abs, "min": min, "max": max,
        "sum": sum, "int": int, "str": str, "float": float,
        "True": True, "False": False, "None": None,
    }
    safe_env.update(env)   # 用户变量覆盖内置名，符合 Python 真实语义
    try:
        # globals 给空 builtins：表达式中只能使用 safe_env 提供的名字
        val = eval(expr, {"__builtins__": {}}, safe_env)
    except NameError as e:
        raise CodeError(f"变量未定义：{e}")
    except TypeError as e:
        raise CodeError(f"类型错误：{e}")
    except IndexError:
        raise CodeError("索引越界：下标超出列表长度")
    except ZeroDivisionError:
        raise CodeError("除数不能为 0")
    except OverflowError:
        raise CodeError("数值超出范围")
    except Exception as e:
        raise CodeError(f"表达式错误：{e}")

    # 值类型白名单：只允许教学需要的数据类型
    # （range 是 range() 函数的返回值，for 循环需要用到）
    if val is None or isinstance(val, (int, float, str, bool, list, range)):
        return val
    raise CodeError("仅支持数字 / 字符串 / 列表类型的值")


# ------------------------------------------------------------------------------
# 代码行解析
# ------------------------------------------------------------------------------
def parse_lines(code_text):
    """
    把代码文本解析成"逻辑行"列表。

    返回: [(indent, code, line_no), ...]
        indent : 行首缩进（空格数，tab 按 4 空格展开）
        code   : 去除缩进和首尾空白的语句文本
        line_no: 原始行号（从 1 开始，用于代码区高亮）

    处理: 空行、注释行（# 开头）跳过不执行，但行号继续保留。
    """
    lines = []
    for i, raw in enumerate(code_text.splitlines(), start=1):
        text = raw.expandtabs(4)               # tab 展开为 4 个空格
        stripped = text.strip()
        if not stripped:                       # 空行：跳过
            continue
        if stripped.startswith("#"):           # 注释行：跳过
            continue
        indent = len(text) - len(text.lstrip(" "))   # 缩进空格数
        lines.append((indent, stripped, i))
    return lines


# ------------------------------------------------------------------------------
# 步骤展开（核心）
# ------------------------------------------------------------------------------
def expand_code(code_text):
    """
    把整段代码"展开"成线性步骤列表（解释器主入口）。

    参数:
        code_text: 用户输入的完整代码文本

    返回:
        (steps, error)
        steps: 步骤列表，每项一个字典：
            line_no : 原始行号（1 起，用于代码区高亮）
            text    : 该行语句文本
            indent  : 缩进
            desc    : 本步骤的中文讲解文字
            env     : 执行后变量环境的深拷贝快照（用于绘制内存面板）
            out     : 到目前为止的 print 输出列表（副本）
            op      : 操作信息（用于高亮变量/列表格子）
        error: None 表示成功；否则为 CodeError 的中文消息字符串
    """
    try:
        lines = parse_lines(code_text)
        steps = []
        outputs = []
        env = {}
        ctx = {"lines": lines}
        execute_statements(0, 0, env, steps, outputs, ctx)
        return steps, None
    except CodeError as e:
        return None, str(e)


def _snapshot(env, outputs, line_no, text, indent, desc, op):
    """构造一个步骤字典：保存执行到这一步时的完整现场。"""
    return {
        "line_no": line_no,
        "text": text,
        "indent": indent,
        "desc": desc,
        "env": copy.deepcopy(env),     # 深拷贝：快照与后续执行互不影响
        "out": list(outputs),          # 输出列表副本
        "op": op,
    }


def find_block_end(ctx, ip):
    """
    找块体结束位置：返回第一个缩进 <= 块引导行缩进的行下标。
    即：块引导行之后的"缩进更大"的行都属于块体。
    """
    lines = ctx["lines"]
    base_indent = lines[ip][0]
    j = ip + 1
    while j < len(lines) and lines[j][0] > base_indent:
        j += 1
    return j


def get_body(ctx, ip, parent_indent, line_no):
    """
    获取块体信息：(body_ip, body_indent)。
        body_ip     : 块体第一行的下标
        body_indent : 块体第一行的实际缩进（决定整个块体的缩进级别）
    若 : 后面没有缩进块体（下一行缩进 <= 父缩进），报"缺少缩进"。
    """
    lines = ctx["lines"]
    body_ip = ip + 1
    if body_ip >= len(lines) or lines[body_ip][0] <= parent_indent:
        raise CodeError(f"第 {line_no} 行：冒号后缺少缩进的代码块（下一行需要缩进）")
    return body_ip, lines[body_ip][0]


def execute_statements(ip, min_indent, env, steps, outputs, ctx):
    """
    递归执行"缩进级别为 min_indent"的语句序列（即一个块体）。

    参数:
        ip        : 当前指令指针（逻辑行下标）
        min_indent: 本块要求的最小缩进
        env       : 变量环境（模拟执行中实时修改）
        steps     : 步骤列表（输出）
        outputs   : print 输出列表
        ctx       : 共享上下文 {"lines": [...]}

    返回:
        执行完成后 ip 应指向的位置（块结束后的下一个逻辑行）

    教学说明:
        这个函数对应 Python 解释器的"执行"概念——
        遇到 for/while/if 时，先执行"块头"判断，再递归执行块体；
        缩进级别就是"块"的边界。
    """
    lines = ctx["lines"]
    n = len(lines)

    while ip < n:
        indent, code, line_no = lines[ip]

        # 缩进比要求的少 → 当前块结束，返回给上层
        if indent < min_indent:
            break
        # 缩进比要求的多 → 没有对应的 for/if 引导，语法错误
        if indent > min_indent:
            raise CodeError(f"第 {line_no} 行：缩进错误（多余的空格）")

        # ======================================================================
        # 块引导语句（行尾带冒号）
        # ======================================================================
        if code.endswith(":"):

            # ---------- for 循环：展开成多次顺序执行 ----------
            if code.startswith("for "):
                m = re.match(r"for\s+(\w+)\s+in\s+(.+):\s*$", code)
                if not m:
                    raise CodeError(f"第 {line_no} 行：for 语句格式错误")
                var_name, iter_expr = m.group(1), m.group(2)
                iterable = eval_expr(iter_expr, env)     # 求值出要遍历的序列
                if not isinstance(iterable, (list, range)):
                    raise CodeError(f"第 {line_no} 行：for 只能遍历列表或 range")
                body_ip, body_indent = get_body(ctx, ip, indent, line_no)
                end_ip = find_block_end(ctx, ip)         # 块体范围
                count = 0
                for item in iterable:                    # 逐个迭代
                    count += 1
                    if count > MAX_LOOP:                 # 死循环保护
                        raise CodeError(f"第 {line_no} 行：循环超过 {MAX_LOOP} 次，可能死循环")
                    env[var_name] = item                 # 循环变量赋值
                    steps.append(_snapshot(env, outputs, line_no, code, indent,
                                           f"进入 for 循环：{var_name} = {item}",
                                           {"type": "for", "var": var_name, "value": item}))
                    execute_statements(body_ip, body_indent, env, steps, outputs, ctx)
                ip = end_ip
                continue

            # ---------- while 循环 ----------
            if code.startswith("while "):
                cond_expr = code[len("while "):].rstrip(":").strip()
                body_ip, body_indent = get_body(ctx, ip, indent, line_no)
                end_ip = find_block_end(ctx, ip)
                count = 0
                # 条件为真就进入循环体，每轮重新判断
                while eval_expr(cond_expr, env):
                    count += 1
                    if count > MAX_LOOP:
                        raise CodeError(f"第 {line_no} 行：循环超过 {MAX_LOOP} 次，可能死循环")
                    steps.append(_snapshot(env, outputs, line_no, code, indent,
                                           f"while 条件成立，进入循环体（第 {count} 次）",
                                           {"type": "while_check", "result": True}))
                    execute_statements(body_ip, body_indent, env, steps, outputs, ctx)
                # 记录退出循环的判定
                steps.append(_snapshot(env, outputs, line_no, code, indent,
                                       "while 条件不成立，退出循环",
                                       {"type": "while_check", "result": False}))
                ip = end_ip
                continue

            # ---------- if / elif / else 分支 ----------
            if code.startswith("if ") or code.startswith("elif "):
                base_indent = indent
                chain = []                 # [(类型, 条件或None, 块体开始, 该行号)]
                cur = ip
                # 收集整条 if 链：if / elif* / else?（它们缩进相同）
                while cur < n:
                    c_indent, c_code, c_line = lines[cur]
                    if c_indent != base_indent:
                        break
                    if c_code.startswith("if "):
                        chain.append(("if", c_code[3:].rstrip(":").strip(), cur + 1, c_line))
                    elif c_code.startswith("elif "):
                        chain.append(("elif", c_code[5:].rstrip(":").strip(), cur + 1, c_line))
                    elif c_code.startswith("else"):
                        chain.append(("else", None, cur + 1, c_line))
                        cur = find_block_end(ctx, cur)   # 跳过 else 块体
                        break
                    else:
                        break
                    cur = find_block_end(ctx, cur)      # 跳到该分支块之后
                end_ip = cur

                executed = False
                for typ, cond, body_ip, head_line in chain:
                    if typ == "else":
                        # 前面所有分支都没成立 → 执行 else
                        if not executed and body_ip < n:
                            # 校验 else 块体存在，并取块体实际缩进
                            if lines[body_ip][0] <= base_indent:
                                raise CodeError(f"第 {head_line} 行：冒号后缺少缩进的代码块")
                            steps.append(_snapshot(env, outputs, head_line, code, indent,
                                                   "进入 else 分支",
                                                   {"type": "if_check", "result": True}))
                            execute_statements(body_ip, lines[body_ip][0], env, steps, outputs, ctx)
                        break
                    if executed:
                        continue           # 已走某分支，其余跳过
                    result = bool(eval_expr(cond, env))
                    steps.append(_snapshot(env, outputs, head_line, code, indent,
                                           f"条件 {cond} 判断为{'真' if result else '假'}",
                                           {"type": "if_check", "result": result}))
                    if result:
                        executed = True
                        if body_ip >= n or lines[body_ip][0] <= base_indent:
                            raise CodeError(f"第 {head_line} 行：冒号后缺少缩进的代码块")
                        execute_statements(body_ip, lines[body_ip][0], env, steps, outputs, ctx)
                ip = end_ip
                continue

            # ---------- 其他以冒号结尾的语句 ----------
            raise CodeError(f"第 {line_no} 行：不支持的语句（目前支持 for / while / if / elif / else）")

        # ======================================================================
        # 普通语句（无冒号）
        # ======================================================================
        execute_simple(code, line_no, indent, env, steps, outputs)
        ip += 1

    return ip


def execute_simple(code, line_no, indent, env, steps, outputs):
    """
    执行一条普通语句，支持：
        print(...)          —— 输出
        name = expr         —— 变量赋值
        lst.append(x)       —— 列表末尾追加
        lst.insert(i, x)    —— 列表指定位置插入
        lst.pop() / pop(i)  —— 弹出元素
        lst.remove(x)       —— 删除指定值
        lst[i] = x          —— 索引赋值
    """
    # ---------- print 输出 ----------
    m = re.match(r"^print\s*\((.*)\)$", code)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")] if m.group(1).strip() else []
        vals = [eval_expr(p, env) for p in parts]          # 逐个求值
        text = " ".join(str(v) for v in vals)
        outputs.append(text)
        steps.append(_snapshot(env, outputs, line_no, code, indent,
                               "print 输出：" + text,
                               {"type": "print", "text": text}))
        return

    # ---------- 列表方法：append ----------
    m = re.match(r"^(\w+)\.append\((.+)\)$", code)
    if m:
        name, expr = m.group(1), m.group(2)
        _check_list(env, name, line_no)
        val = eval_expr(expr, env)
        env[name].append(val)
        steps.append(_snapshot(env, outputs, line_no, code, indent,
                               f"{name}.append({val})：末尾追加 {val}",
                               {"type": "list_append", "name": name, "value": val}))
        return

    # ---------- 列表方法：insert ----------
    m = re.match(r"^(\w+)\.insert\((.+),\s*(.+)\)$", code)
    if m:
        name, pos_e, val_e = m.group(1), m.group(2), m.group(3)
        _check_list(env, name, line_no)
        pos = int(eval_expr(pos_e, env))
        val = eval_expr(val_e, env)
        env[name].insert(pos, val)
        steps.append(_snapshot(env, outputs, line_no, code, indent,
                               f"{name}.insert({pos}, {val})：在位置 {pos} 插入 {val}",
                               {"type": "list_insert", "name": name, "index": pos, "value": val}))
        return

    # ---------- 列表方法：pop() ----------
    m = re.match(r"^(\w+)\.pop\(\)$", code)
    if m:
        name = m.group(1)
        _check_list(env, name, line_no)
        if not env[name]:
            raise CodeError(f"第 {line_no} 行：{name} 是空列表，不能 pop")
        val = env[name].pop()
        steps.append(_snapshot(env, outputs, line_no, code, indent,
                               f"{name}.pop()：弹出最后一个元素 {val}",
                               {"type": "list_pop", "name": name, "value": val}))
        return

    # ---------- 列表方法：pop(i) ----------
    m = re.match(r"^(\w+)\.pop\((.+)\)$", code)
    if m:
        name, pos_e = m.group(1), m.group(2)
        _check_list(env, name, line_no)
        pos = int(eval_expr(pos_e, env))
        val = env[name].pop(pos)
        steps.append(_snapshot(env, outputs, line_no, code, indent,
                               f"{name}.pop({pos})：弹出位置 {pos} 的元素 {val}",
                               {"type": "list_pop", "name": name, "index": pos, "value": val}))
        return

    # ---------- 列表方法：remove ----------
    m = re.match(r"^(\w+)\.remove\((.+)\)$", code)
    if m:
        name, expr = m.group(1), m.group(2)
        _check_list(env, name, line_no)
        val = eval_expr(expr, env)
        if val not in env[name]:
            raise CodeError(f"第 {line_no} 行：列表中没有 {val}，无法 remove")
        env[name].remove(val)
        steps.append(_snapshot(env, outputs, line_no, code, indent,
                               f"{name}.remove({val})：删除第一个值为 {val} 的元素",
                               {"type": "list_remove", "name": name, "value": val}))
        return

    # ---------- 索引赋值 lst[i] = x ----------
    m = re.match(r"^(\w+)\s*\[\s*([^\[\]]+)\s*\]\s*=\s*(.+)$", code)
    if m:
        name, idx_e, val_e = m.group(1), m.group(2), m.group(3)
        _check_list(env, name, line_no)
        idx = int(eval_expr(idx_e, env))
        val = eval_expr(val_e, env)
        env[name][idx] = val
        steps.append(_snapshot(env, outputs, line_no, code, indent,
                               f"{name}[{idx}] = {val}：修改位置 {idx} 的值为 {val}",
                               {"type": "list_set", "name": name, "index": idx, "value": val}))
        return

    # ---------- 变量赋值 name = expr ----------
    m = re.match(r"^(\w+)\s*=\s*(.+)$", code)
    if m:
        name, expr = m.group(1), m.group(2)
        val = eval_expr(expr, env)
        env[name] = val
        # 描述：字符串带引号显示更清楚
        desc_val = f'"{val}"' if isinstance(val, str) else str(val)
        steps.append(_snapshot(env, outputs, line_no, code, indent,
                               f"变量 {name} = {desc_val}",
                               {"type": "assign", "name": name, "value": val}))
        return

    # ---------- 不支持的语句 ----------
    raise CodeError(f"第 {line_no} 行：不支持的语句（支持：变量赋值 / 列表操作 / print / for / while / if）")


def _check_list(env, name, line_no):
    """确认变量 name 是列表，否则报中文错误。"""
    if name not in env:
        raise CodeError(f"第 {line_no} 行：变量 {name} 未定义")
    if not isinstance(env[name], list):
        raise CodeError(f"第 {line_no} 行：{name} 不是列表，不能执行列表操作")
