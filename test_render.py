# -*- coding: utf-8 -*-
"""
无头渲染验证：在 dummy 视频驱动下渲染界面各状态并截图。
用于验证 main.py 的绘制逻辑（代码区 / 内存面板 / 描述栏）无运行时报错。
"""
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import main as app
from interpreter import expand_code

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_shots")
os.makedirs(OUT_DIR, exist_ok=True)


def main():
    pygame.init()
    screen = pygame.display.set_mode((app.WIDTH, app.HEIGHT))

    # ---------- 1. 编辑模式：示例1 最终状态（实时预览） ----------
    editor = app.Editor(app.EXAMPLES["1"][1])
    steps, err = expand_code(editor.text)
    cur = steps[-1]
    screen.fill(app.COL_BG)
    app.draw_code_area(screen, editor, "edit", cur["line_no"], None)
    app.draw_memory_panel(screen, cur["env"], cur["op"], cur["out"])
    app.draw_desc_bar(screen, "实时预览：" + cur["desc"])
    app.draw_hint(screen, app.HINT_EDIT)
    pygame.display.flip()
    pygame.image.save(screen, os.path.join(OUT_DIR, "1_edit_example1.png"))

    # ---------- 2. 演示模式：示例2 中间某步（单步回放 + 执行行高亮） ----------
    editor2 = app.Editor(app.EXAMPLES["2"][1])
    steps2, err2 = expand_code(editor2.text)
    assert not err2, err2
    idx = 12
    cur2 = steps2[idx]
    screen.fill(app.COL_BG)
    app.draw_code_area(screen, editor2, "demo", cur2["line_no"], None)
    app.draw_memory_panel(screen, cur2["env"], cur2["op"], cur2["out"])
    app.draw_desc_bar(screen, f"第 {idx} / {len(steps2) - 1} 步   {cur2['desc']}")
    app.draw_hint(screen, app.HINT_DEMO)
    pygame.display.flip()
    pygame.image.save(screen, os.path.join(OUT_DIR, "2_demo_example2.png"))

    # ---------- 3. 演示模式：示例3 最终一步（if 分支完成） ----------
    editor3 = app.Editor(app.EXAMPLES["3"][1])
    steps3, err3 = expand_code(editor3.text)
    assert not err3, err3
    cur3 = steps3[-1]
    screen.fill(app.COL_BG)
    app.draw_code_area(screen, editor3, "demo", cur3["line_no"], None)
    app.draw_memory_panel(screen, cur3["env"], cur3["op"], cur3["out"])
    app.draw_desc_bar(screen, "第 %d / %d 步   %s" % (len(steps3) - 1, len(steps3) - 1, cur3["desc"]))
    app.draw_hint(screen, app.HINT_DEMO)
    pygame.display.flip()
    pygame.image.save(screen, os.path.join(OUT_DIR, "3_demo_example3.png"))

    # ---------- 4. 错误状态：显示中文错误 ----------
    editor4 = app.Editor("a = x + 1")
    _, err4 = expand_code(editor4.text)
    screen.fill(app.COL_BG)
    app.draw_code_area(screen, editor4, "edit", None, None)
    app.draw_memory_panel(screen, {}, None, [])
    app.draw_desc_bar(screen, "⚠ " + err4, is_error=True)
    app.draw_hint(screen, app.HINT_EDIT)
    pygame.display.flip()
    pygame.image.save(screen, os.path.join(OUT_DIR, "4_error_state.png"))

    # ---------- 5. Editor 文本操作冒烟测试 ----------
    ed = app.Editor("ab")
    ed.insert("c")                # "abc"
    assert ed.text == "abc"
    ed.move_left()
    ed.move_left()                # 光标到 1
    ed.insert("X")                # "aXbc"
    assert ed.text == "aXbc"
    ed.backspace()                # "abc"，光标回到 1
    assert ed.text == "abc" and ed.cursor == 1
    ed.move_up()                  # 第一行，不移动
    assert ed.cursor == 1
    ed.move_down()                # 最后一行，光标到末尾
    assert ed.cursor == 3
    print("Editor 文本操作 ✅")

    print("ALL RENDER OK")
    pygame.quit()


if __name__ == "__main__":
    main()
