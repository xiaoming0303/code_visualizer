# -*- coding: utf-8 -*-
"""
解释器单元测试：验证简易教学解释器的核心功能。

运行：python test_interpreter.py
覆盖：变量赋值 / 列表操作 / for / while / if 分支 / 嵌套 / 错误处理 / 死循环保护
"""
import sys
sys.path.insert(0, ".")
from interpreter import expand_code


def show(name, steps, err):
    """打印测试结果。"""
    if err:
        print(f"  ❌ {name}  →  错误: {err}")
        return False
    # 打印最终环境与输出
    last = steps[-1]
    print(f"  ✅ {name}  步骤数={len(steps)}  最终env={last['env']}  输出={last['out']}")
    return True


print("=" * 60)
print("解释器单元测试")
print("=" * 60)

ok = True

# 1. 变量赋值与运算
s, e = expand_code("a = 10\nb = a * 2\ns = \"hi\"")
ok &= show("变量赋值与运算", s, e)
assert not e and s[-1]["env"] == {"a": 10, "b": 20, "s": "hi"}

# 2. 列表操作
s, e = expand_code("lst = [1, 3, 5]\nlst.append(7)\nlst.insert(1, 99)\nlst.pop()")
ok &= show("列表 append/insert/pop", s, e)
assert not e and s[-1]["env"]["lst"] == [1, 99, 3, 5]

# 3. for 循环（range）
s, e = expand_code("sum = 0\nfor i in range(1, 5):\n    sum = sum + i\nprint(sum)")
ok &= show("for 循环 range(1,5)", s, e)
assert not e and s[-1]["env"]["sum"] == 10
assert s[-1]["out"] == ["10"]

# 4. for 循环（遍历列表）
s, e = expand_code("total = 0\nfor x in [10, 20, 30]:\n    total = total + x")
ok &= show("for 循环遍历列表", s, e)
assert not e and s[-1]["env"]["total"] == 60

# 5. while 循环
s, e = expand_code("t = 1\nwhile t < 10:\n    t = t * 2")
ok &= show("while 循环", s, e)
assert not e and s[-1]["env"]["t"] == 16

# 6. if / else 分支
s, e = expand_code("score = 85\nif score >= 90:\n    r = \"A\"\nelse:\n    r = \"B\"")
ok &= show("if/else 分支", s, e)
assert not e and s[-1]["env"]["r"] == "B"

# 7. if / elif / else 链
s, e = expand_code("n = 5\nif n == 1:\n    r = 1\nelif n == 5:\n    r = 2\nelse:\n    r = 3")
ok &= show("if/elif/else 链", s, e)
assert not e and s[-1]["env"]["r"] == 2

# 8. 嵌套 if
s, e = expand_code("score = 85\nif score >= 60:\n    if score >= 90:\n        r = \"A\"\n    else:\n        r = \"B\"\nelse:\n    r = \"C\"")
ok &= show("嵌套 if", s, e)
assert not e and s[-1]["env"]["r"] == "B"

# 9. 嵌套 for
s, e = expand_code("n = 0\nfor i in range(3):\n    for j in range(2):\n        n = n + 1")
ok &= show("嵌套 for", s, e)
assert not e and s[-1]["env"]["n"] == 6

# 10. print 多参数 + 字符串拼接
s, e = expand_code("a = 3\nb = 4\nprint(\"和 =\", a + b)\nprint(\"abc\" + \"def\")")
ok &= show("print 多参数/字符串拼接", s, e)
assert not e and s[-1]["out"] == ["和 = 7", "abcdef"]

# 11. 列表索引取值/赋值
s, e = expand_code("lst = [1, 2, 3]\nlst[0] = 99\nx = lst[1]")
ok &= show("列表索引", s, e)
assert not e and s[-1]["env"]["lst"] == [99, 2, 3] and s[-1]["env"]["x"] == 2

# 12. 未定义变量报错
s, e = expand_code("a = x + 1")
assert e and "未定义" in e
print("  ✅ 未定义变量应报错 →", e)

# 13. 死循环保护
s, e = expand_code("n = 0\nwhile n < 100000:\n    n = n + 1")
assert e and "死循环" in e
print("  ✅ 死循环保护 →", e)

# 14. 非法语句报错
s, e = expand_code("import os")
assert e
print("  ✅ 敏感语句应报错 →", e)

# 15. 缩进错误
s, e = expand_code("a = 1\n    b = 2")
assert e and "缩进" in e
print("  ✅ 缩进错误应报错 →", e)

# 16. 注释与空行跳过
s, e = expand_code("# 这是注释\na = 1\n\n# 空行已跳过\nb = a + 1")
ok &= show("注释/空行跳过", s, e)
assert not e and s[-1]["env"] == {"a": 1, "b": 2}

# 17. 步骤快照独立性（修改不影响历史步骤）
s, e = expand_code("a = 1\na = 2\na = 3")
ok &= show("步骤快照独立", s, e)
assert not e and s[0]["env"] == {"a": 1} and s[1]["env"] == {"a": 2} and s[2]["env"] == {"a": 3}

print("=" * 60)
print("全部通过 ✅" if ok else "存在失败 ❌")
sys.exit(0 if ok else 1)
