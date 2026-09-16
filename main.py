# -*- coding: utf-8 -*-
"""
================================================================================
 Python 语法可视化编辑器（Pygame 桌面版）
================================================================================

 【项目定位】
     面向浙江信息科技《数据与计算》模块的 Python 基础语法教学工具。
     学生可以在窗口内**直接编辑 Python 代码**，
     右侧**实时可视化**变量、列表、循环、分支的执行结果；
     切换演示模式后，可以**单步回放**每一步执行，观察内存变化。

 【核心特点】
     ✅ 左边写代码，右边看结果 —— 修改代码，可视化画面立即跟着变
     ✅ 自定义安全解释器 —— 只支持教学语法，不执行任意系统命令
     ✅ 单步回放 —— 演示模式下 空格播放 / ←→ 单步，逐行看内存变化
     ✅ 内置三套示例 —— 变量与列表 / for与while / if分支

 【运行方式】
     python main.py

 【按键说明】
     编辑模式（默认）：
        直接输入            —— 编辑代码（支持中文输入法）
        Enter               —— 换行
        Backspace / Delete  —— 删除字符
        方向键              —— 移动光标
        主键盘 1 / 2 / 3    —— 载入三套示例代码（输入数字请用小键盘）
        Tab                 —— 切换到演示模式
        ESC                 —— 退出
     演示模式：
        空格                —— 播放 / 暂停
        ← / →               —— 单步回退 / 单步前进
        ↑ / ↓               —— 调速
        R                   —— 重置回第一步
        Tab                 —— 返回编辑模式
        ESC                 —— 退出

 【模块结构】
     interpreter.py   —— 简易教学解释器（解析代码 → 展开成步骤 + 内存快照）
     main.py          —— Pygame 应用（文本编辑器、内存可视化、主循环）
================================================================================
"""
import sys
import pygame

from interpreter import expand_code

# ------------------------------------------------------------------------------
# 窗口与布局常量
# ------------------------------------------------------------------------------
WIDTH, HEIGHT = 1200, 640

# 四个区域：代码编辑器 / 内存面板 / 描述栏 / 底部提示栏
CODE_RECT = (20, 20, 560, 470)
MEM_RECT = (600, 20, 580, 470)
DESC_RECT = (20, 505, 1160, 60)

# 代码区内部参数
LINE_H = 26                 # 每行代码高度
CODE_FONT_SIZE = 20         # 代码字号
LINE_NO_W = 46              # 行号列宽度
CODE_TOP = 58               # 代码第一行的 y 坐标
VISIBLE_LINES = 16          # 代码区可见行数

# 颜色常量
COL_BG      = (244, 247, 250)
COL_TEXT    = (40, 48, 60)
COL_SUB     = (120, 130, 145)
COL_WHITE   = (255, 255, 255)
COL_PANEL   = (255, 255, 255)
COL_BLUE    = (70, 130, 220)
COL_GREEN   = (76, 175, 120)
COL_ORANGE  = (242, 135, 60)
COL_RED     = (228, 80, 80)
COL_YELLOW  = (240, 185, 60)
COL_PURPLE  = (140, 105, 215)
COL_HINT    = (28, 34, 44)
COL_HINT_T  = (222, 228, 236)
COL_EXEC_BG = (255, 244, 200)   # 当前执行行背景
COL_GRAY    = (210, 216, 226)

# ------------------------------------------------------------------------------
# 字体工具（独立实现，保证项目自包含）
# ------------------------------------------------------------------------------
_FONT_CACHE = {}

def load_font(size, bold=False):
    """加载支持中文的字体，带缓存（依次尝试微软雅黑/黑体/宋体）。"""
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    font = None
    for name in ("microsoftyahei", "simhei", "simsun", "dengxian"):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f is not None:
                font = f
                break
        except Exception:
            continue
    if font is None:
        font = pygame.font.Font(None, size)
    _FONT_CACHE[key] = font
    return font


def draw_text(screen, text, size, color, x, y, bold=False, align="left"):
    """绘制一行文本；align: left / center / right。"""
    font = load_font(size, bold)
    surf = font.render(str(text), True, color)
    rect = surf.get_rect()
    if align == "center":
        rect.midtop = (int(x), int(y))
    elif align == "right":
        rect.topright = (int(x), int(y))
    else:
        rect.topleft = (int(x), int(y))
    screen.blit(surf, rect)
    return rect


def draw_rect(screen, rect, color, radius=8, width=0):
    """圆角矩形辅助函数。"""
    pygame.draw.rect(screen, color, rect, width=width, border_radius=radius)


# ==============================================================================
# 迷你文本编辑器（支持中文输入、光标移动、退格删除）
# ==============================================================================
class Editor:
    """
    极简文本编辑器：维护一段文本和一个光标位置（字符索引）。

    支持：
        insert(ch)    —— 在光标处插入字符
        backspace()   —— 删除光标前一个字符
        delete()      —— 删除光标后一个字符
        newline()     —— 在光标处换行
        方向键移动光标、光标可见性滚动
    """

    def __init__(self, default_text=""):
        self.text = default_text
        self.cursor = len(default_text)     # 光标 = 字符索引
        self.scroll = 0                     # 编辑区顶部显示的行号（滚动偏移）

    # ---------- 文本操作 ----------

    def insert(self, ch):
        """在光标位置插入字符（含中文）。"""
        self.text = self.text[:self.cursor] + ch + self.text[self.cursor:]
        self.cursor += len(ch)
        self._ensure_visible()

    def backspace(self):
        """删除光标前一个字符。"""
        if self.cursor > 0:
            self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
            self.cursor -= 1
            self._ensure_visible()

    def delete(self):
        """删除光标后一个字符。"""
        if self.cursor < len(self.text):
            self.text = self.text[:self.cursor] + self.text[self.cursor + 1:]
            self._ensure_visible()

    def newline(self):
        """在光标处换行。"""
        self.insert("\n")

    # ---------- 光标移动 ----------

    def move_left(self):
        if self.cursor > 0:
            self.cursor -= 1
            self._ensure_visible()

    def move_right(self):
        if self.cursor < len(self.text):
            self.cursor += 1
            self._ensure_visible()

    def move_up(self):
        """光标上移一行（尽量保持列位置不变）。"""
        row, col = self.cursor_row_col()
        if row == 0:
            return
        cur_start = self._line_start(row)
        prev_start = self._line_start(row - 1)
        prev_len = cur_start - prev_start - 1          # 上一行长度
        self.cursor = prev_start + min(col, prev_len)
        self._ensure_visible()

    def move_down(self):
        """光标下移一行（尽量保持列位置不变）。"""
        row, col = self.cursor_row_col()
        if row >= self.line_count() - 1:
            self.cursor = len(self.text)
            return
        nxt_start = self._line_start(row + 1)
        nxt_len = len(self.text) - nxt_start
        if row + 1 < self.line_count() - 1:
            nxt_len -= 1                              # 非最后一行要减去换行符
        self.cursor = nxt_start + min(col, nxt_len)
        self._ensure_visible()

    # ---------- 辅助计算 ----------

    def _line_start(self, row):
        """第 row 行的起始字符索引（0 基）。"""
        idx = 0
        for _ in range(row):
            idx = self.text.find("\n", idx) + 1
        return idx

    def line_count(self):
        """总行数（空文本视为 1 行）。"""
        return self.text.count("\n") + 1

    def cursor_row_col(self):
        """返回光标所在 (行, 列)。"""
        text = self.text
        row = text.count("\n", 0, self.cursor)
        last_nl = text.rfind("\n", 0, self.cursor)
        col = self.cursor - (last_nl + 1) if last_nl != -1 else self.cursor
        return row, col

    def _ensure_visible(self):
        """滚动编辑区，确保光标所在行可见。"""
        row, _ = self.cursor_row_col()
        if row < self.scroll:
            self.scroll = row
        if row >= self.scroll + VISIBLE_LINES:
            self.scroll = row - VISIBLE_LINES + 1

    def line(self, row):
        """返回第 row 行的文本（不含换行符）。"""
        start = self._line_start(row)
        end = self.text.find("\n", start)
        if end == -1:
            end = len(self.text)
        return self.text[start:end]


# ==============================================================================
# 三套内置示例代码（覆盖核心语法教学）
# ==============================================================================
EXAMPLES = {
    "1": ("变量与列表",
          "a = 10\n"
          "b = a * 2\n"
          "lst = [1, 3, 5]\n"
          "lst.append(b)\n"
          "lst.insert(1, 99)\n"
          "print(lst)"),
    "2": ("for / while 循环",
          "sum = 0\n"
          "for i in range(1, 6):\n"
          "    sum = sum + i\n"
          "    print(i)\n"
          "print(\"1~5的和 =\", sum)\n"
          "\n"
          "t = 1\n"
          "while t < 10:\n"
          "    t = t * 2\n"
          "print(\"翻倍结果 =\", t)"),
    "3": ("if 分支",
          "score = 85\n"
          "if score >= 90:\n"
          "    print(\"优秀\")\n"
          "else:\n"
          "    if score >= 60:\n"
          "        print(\"及格\")\n"
          "    else:\n"
          "        print(\"不及格\")\n"
          "print(\"成绩判断结束\")"),
}

HINT_EDIT = "编辑模式 | Tab:进入演示  主键盘1/2/3:示例代码  数字键盘:输入数字 方向键:移动光标  Enter:换行  Backspace:删除  ESC:退出"
HINT_DEMO = "演示模式 | Tab:返回编辑  空格:播放/暂停  ←/→:单步  ↑/↓:调速  R:重置  ESC:退出"


# ==============================================================================
# 绘制：代码区
# ==============================================================================
def draw_code_area(screen, editor, mode, exec_line, fonts):
    """
    绘制左侧代码编辑器。

    参数:
        exec_line: 当前执行行号（1 基；None 表示不高亮）
    """
    x0, y0, w, h = CODE_RECT
    draw_rect(screen, (x0, y0, w, h), COL_PANEL, radius=12)

    # 标题 + 模式指示
    draw_text(screen, "代码编辑器", 22, COL_TEXT, x0 + 18, y0 + 12, bold=True)
    mode_text = "● 编辑中（实时预览）" if mode == "edit" else "● 演示中（单步回放）"
    mode_color = COL_GREEN if mode == "edit" else COL_ORANGE
    draw_text(screen, mode_text, 17, mode_color, x0 + w - 18, y0 + 16, align="right")

    # 逐行绘制代码
    for r in range(editor.scroll, min(editor.scroll + VISIBLE_LINES, editor.line_count())):
        row = r - editor.scroll
        yy = CODE_TOP + row * LINE_H
        line_no = r + 1
        line_text = editor.line(r)

        # 当前执行行背景高亮
        if exec_line == line_no and mode == "demo":
            draw_rect(screen, (x0 + 6, yy - 3, w - 12, LINE_H), COL_EXEC_BG, radius=5)

        # 行号
        draw_text(screen, str(line_no), 14, COL_GREEN if exec_line == line_no else COL_SUB,
                  x0 + LINE_NO_W - 14, yy, align="right", bold=(exec_line == line_no))
        # 代码文本
        draw_text(screen, line_text if line_text else " ", CODE_FONT_SIZE,
                  COL_TEXT, x0 + LINE_NO_W + 6, yy)

    # 光标（编辑模式显示，闪烁效果）
    if mode == "edit" and (pygame.time.get_ticks() // 500) % 2 == 0:
        row, col = editor.cursor_row_col()
        if editor.scroll <= row < editor.scroll + VISIBLE_LINES:
            line_text = editor.line(row)
            prefix = line_text[:col]
            cx = x0 + LINE_NO_W + 6 + load_font(CODE_FONT_SIZE).size(prefix)[0]
            cy = CODE_TOP + (row - editor.scroll) * LINE_H
            pygame.draw.line(screen, COL_RED, (cx, cy), (cx, cy + LINE_H - 4), 2)


# ==============================================================================
# 绘制：内存可视化面板
# ==============================================================================
def draw_memory_panel(screen, env, op, out_lines):
    """
    绘制右侧内存可视化面板。

    展示内容:
        · 每个变量一个"盒子"：数值变量蓝色盒 / 字符串绿色盒 / 列表方格组
        · 最近操作的元素用橙色高亮
        · 底部显示 print 输出区
    """
    x0, y0, w, h = MEM_RECT
    draw_rect(screen, (x0, y0, w, h), COL_PANEL, radius=12)
    draw_text(screen, "内存可视化（变量 / 列表 / 输出）", 22, COL_TEXT, x0 + 18, y0 + 12, bold=True)

    # ---- 变量区 ----
    var_top = y0 + 56
    var_bottom = y0 + 330          # 变量区底部
    x = x0 + 26
    y = var_top
    max_vars = 4                   # 最多显示 4 个变量块（教学代码足够）
    shown = 0

    for name, val in env.items():
        if y > var_bottom - 40 or shown >= max_vars:
            break
        # 变量名
        draw_text(screen, name, 20, COL_TEXT, x, y, bold=True)
        draw_text(screen, "=", 20, COL_SUB, x + 64, y)

        val_x = x + 88

        if isinstance(val, list):
            # ---------- 列表：画一排方格 ----------
            box_y = y + 22
            cell_w, cell_h, gap = 46, 44, 5
            shown_cells = min(len(val), 8)          # 最多显示 8 个格子
            for i in range(shown_cells):
                bx = val_x + i * (cell_w + gap)
                # 高亮最近操作的目标格子
                hl = False
                if op and op.get("name") == name:
                    if op["type"] in ("list_append",) and i == len(val) - 1:
                        hl = True
                    if op["type"] in ("list_insert", "list_set") and op.get("index") == i:
                        hl = True
                color = COL_ORANGE if hl else COL_BLUE
                draw_rect(screen, (bx, box_y, cell_w, cell_h), color, radius=6)
                # 格子内显示值
                item = val[i]
                item_text = str(item) if not isinstance(item, str) else item
                draw_text(screen, item_text[:4], 17, COL_WHITE,
                          bx + cell_w / 2, box_y + 10, align="center", bold=True)
                # 格子下方显示下标
                draw_text(screen, f"[{i}]", 12, COL_SUB, bx + cell_w / 2, box_y + cell_h + 1,
                          align="center")
            if len(val) > shown_cells:
                draw_text(screen, f"…共{len(val)}项", 14, COL_SUB,
                          val_x + shown_cells * (cell_w + gap), box_y + 12)
            y += 22 + cell_h + 17 + 12
        else:
            # ---------- 简单值：画一个盒子 ----------
            box_y = y + 22
            if isinstance(val, str):
                color = COL_GREEN
                text = val if len(val) <= 8 else val[:8] + "…"
                text = '"' + text + '"'
            elif isinstance(val, bool):
                color = COL_PURPLE
                text = str(val)
            else:
                color = COL_BLUE
                text = str(val)
            # 最近赋值给该变量的盒子加橙色描边
            border = 3 if (op and op.get("type") == "assign" and op.get("name") == name) else 0
            draw_rect(screen, (val_x, box_y, 150, 42), color, radius=7)
            if border:
                pygame.draw.rect(screen, COL_ORANGE, (val_x - 2, box_y - 2, 154, 46),
                                 width=2, border_radius=9)
            draw_text(screen, text, 20, COL_WHITE, val_x + 75, box_y + 9, align="center", bold=True)
            y += 22 + 42 + 14
        shown += 1

    if not env:
        draw_text(screen, "（暂无变量，执行代码后这里会显示）", 18, COL_SUB, x, var_top + 10)

    # ---- 输出区（底部）----
    out_top = y0 + 345
    draw_text(screen, "程序输出", 19, COL_TEXT, x0 + 18, out_top, bold=True)
    pygame.draw.line(screen, (225, 231, 240), (x0 + 18, out_top + 24), (x0 + w - 18, out_top + 24), 2)
    if out_lines:
        # 显示最后 5 行输出
        for i, line in enumerate(out_lines[-5:]):
            yy = out_top + 32 + i * 20
            if yy > y0 + h - 8:
                break
            draw_text(screen, line[:40], 16, COL_TEXT, x0 + 22, yy)
    else:
        draw_text(screen, "（无输出）", 16, COL_SUB, x0 + 22, out_top + 32)


# ==============================================================================
# 绘制：描述栏 + 底部提示栏
# ==============================================================================
def draw_desc_bar(screen, text, is_error=False):
    """描述栏：当前步骤讲解 / 错误信息。"""
    x0, y0, w, h = DESC_RECT
    draw_rect(screen, (x0, y0, w, h), COL_PANEL, radius=10)
    color = COL_RED if is_error else COL_TEXT
    draw_text(screen, text if text else " ", 21, color, x0 + 18, y0 + 16, bold=True)


def draw_hint(screen, text):
    """底部提示栏。"""
    bar = pygame.Rect(0, HEIGHT - 44, WIDTH, 44)
    pygame.draw.rect(screen, COL_HINT, bar)
    draw_text(screen, text, 19, COL_HINT_T, 20, HEIGHT - 35)


# ==============================================================================
# 主程序
# ==============================================================================
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Python 语法可视化编辑器 —— 修改代码，实时看结果")
    clock = pygame.time.Clock()
    try:
        pygame.key.start_text_input()          # 启用文本输入（支持中文输入法）
        pygame.key.set_repeat(400, 40)         # 按住方向键/退格可连续操作
    except Exception:
        pass

    # ---- 状态 ----
    editor = Editor(EXAMPLES["1"][1])          # 默认载入示例 1
    mode = "edit"                              # "edit" 编辑 / "demo" 演示
    # 编辑模式实时预览结果
    preview_steps = []
    preview_error = None
    # 演示模式状态
    demo_steps = []
    demo_idx = 0
    demo_playing = False
    demo_speed = 5

    def reparse():
        """重新解析当前代码（编辑模式实时预览 / 演示模式准备步骤）。"""
        nonlocal preview_steps, preview_error
        preview_steps, preview_error = expand_code(editor.text)

    reparse()

    running = True
    while running:
        # ======================================================================
        # 事件处理
        # ======================================================================
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            # ---- 文本输入（编辑模式）----
            if event.type == pygame.TEXTINPUT and mode == "edit":
                ch = event.text
                if ch and ch not in ("\t", "\r", "\n"):   # 过滤控制字符
                    editor.insert(ch)
                    reparse()
                continue

            if event.type != pygame.KEYDOWN:
                continue

            key = event.key

            if key == pygame.K_ESCAPE:
                running = False
                continue

            if mode == "edit":
                # ============ 编辑模式按键 ============
                if key == pygame.K_TAB:
                    # 切换到演示模式：先解析当前代码
                    steps, err = expand_code(editor.text)
                    if err:
                        preview_error = err          # 有错误则不切换，显示错误
                    else:
                        demo_steps = steps
                        demo_idx = 0
                        demo_playing = False
                        mode = "demo"
                elif key == pygame.K_RETURN:
                    editor.newline()
                    reparse()
                elif key == pygame.K_BACKSPACE:
                    editor.backspace()
                    reparse()
                elif key == pygame.K_DELETE:
                    editor.delete()
                    reparse()
                elif key == pygame.K_LEFT:
                    editor.move_left()
                elif key == pygame.K_RIGHT:
                    editor.move_right()
                elif key == pygame.K_UP:
                    editor.move_up()
                elif key == pygame.K_DOWN:
                    editor.move_down()
                elif key == pygame.K_1:
                    editor = Editor(EXAMPLES["1"][1]); reparse()
                elif key == pygame.K_2:
                    editor = Editor(EXAMPLES["2"][1]); reparse()
                elif key == pygame.K_3:
                    editor = Editor(EXAMPLES["3"][1]); reparse()
            else:
                # ============ 演示模式按键 ============
                if key == pygame.K_TAB:
                    mode = "edit"                    # 返回编辑，保留演示状态
                    reparse()
                elif key == pygame.K_SPACE:
                    if demo_idx >= len(demo_steps) - 1:
                        demo_idx = 0
                    demo_playing = not demo_playing
                elif key == pygame.K_LEFT and demo_idx > 0:
                    demo_idx -= 1
                    demo_playing = False
                elif key == pygame.K_RIGHT and demo_idx < len(demo_steps) - 1:
                    demo_idx += 1
                    demo_playing = False
                elif key == pygame.K_UP:
                    demo_speed = min(30, demo_speed + 2)
                elif key == pygame.K_DOWN:
                    demo_speed = max(1, demo_speed - 2)
                elif key == pygame.K_r:
                    demo_idx = 0
                    demo_playing = False

        # ======================================================================
        # 自动播放推进（演示模式）
        # ======================================================================
        if mode == "demo" and demo_playing:
            for _ in range(demo_speed):
                if demo_idx >= len(demo_steps) - 1:
                    demo_playing = False
                    break
                demo_idx += 1

        # ======================================================================
        # 计算当前要展示的步骤
        # ======================================================================
        if mode == "demo":
            if demo_steps:
                cur = demo_steps[demo_idx]
                exec_line = cur["line_no"]
                desc = f"第 {demo_idx} / {len(demo_steps) - 1} 步   {cur['desc']}"
                is_error = False
            else:
                cur = None
                exec_line = None
                desc = "没有可执行的代码"
                is_error = False
        else:
            if preview_error:
                cur = None
                exec_line = None
                desc = "⚠ " + preview_error
                is_error = True
            elif preview_steps:
                cur = preview_steps[-1]              # 预览：显示最终结果
                exec_line = cur["line_no"]
                desc = "实时预览（执行到最后）：" + cur["desc"]
                is_error = False
            else:
                cur = None
                exec_line = None
                desc = "没有可执行的代码（输入代码或按 1/2/3 载入示例）"
                is_error = False

        env = cur["env"] if cur else {}
        out_lines = cur["out"] if cur else []
        op = cur["op"] if cur else None

        # ======================================================================
        # 渲染
        # ======================================================================
        screen.fill(COL_BG)
        draw_code_area(screen, editor, mode, exec_line, None)
        draw_memory_panel(screen, env, op, out_lines)
        draw_desc_bar(screen, desc, is_error)
        draw_hint(screen, HINT_EDIT if mode == "edit" else HINT_DEMO)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
