import pygame
import threading
import time
import os

INIT_W, INIT_H = 800, 480
FPS = 10

BG       = (10,  12,  20)
PANEL    = (18,  22,  36)
ACCENT   = (0,  210, 180)
WARN     = (255, 180,  30)
ALERT    = (220,  50,  50)
TEXT_PRI = (220, 230, 255)
TEXT_SEC = (100, 120, 160)
BAR_COL  = (0,  180, 160)
BAR_BG   = (30,  36,  52)

_state = {
    "event_word":  None,
    "event_time":  None,
    "event_count": 0,
    "channels":    [0] * 18,
    "trig_rate":   0,
    "temp":        None,
    "pressure":    None,
    "flash":       0,
}
_lock    = threading.Lock()
_running = False
_thread  = None


def init():
    global _running, _thread
    _running = True
    _thread  = threading.Thread(target=_run, daemon=True)
    _thread.start()

def stop():
    global _running
    _running = False

def update_event(word: int, timestamp: str, temp=None, pressure=None):
    with _lock:
        _state["event_word"]   = word
        _state["event_time"]   = timestamp
        _state["event_count"] += 1
        _state["temp"]         = temp
        _state["pressure"]     = pressure
        _state["flash"]        = FPS * 2

def update_monitor(channels, trig_rate, temp=None, pressure=None):
    with _lock:
        _state["channels"]  = list(channels[:18])
        _state["trig_rate"] = trig_rate
        _state["temp"]      = temp
        _state["pressure"]  = pressure


def _make_fonts(h):
    scale     = h / 480
    sz_large  = max(10, int(26 * scale))
    sz_medium = max(8,  int(16 * scale))
    sz_small  = max(6,  int(12 * scale))
    return (
        pygame.font.SysFont("dejavusansmono", sz_large,  bold=True),
        pygame.font.SysFont("dejavusansmono", sz_medium),
        pygame.font.SysFont("dejavusansmono", sz_small),
    )


def _run():
    os.environ['SDL_VIDEO_WINDOW_POS'] = '0,0'
    pygame.init()
    screen = pygame.display.set_mode((INIT_W, INIT_H), pygame.RESIZABLE)
    pygame.display.set_caption("mini_cortex")
    clock     = pygame.time.Clock()
    fonts     = _make_fonts(INIT_H)
    last_size = (INIT_W, INIT_H)

    while _running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
            if event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

        W, H = screen.get_size()
        if (W, H) != last_size:
            fonts     = _make_fonts(H)
            last_size = (W, H)

        font_large, font_medium, font_small = fonts
        header_h = max(36, int(H * 0.10))
        left_w   = int(W * 0.60)
        right_w  = W - left_w

        with _lock:
            state = dict(_state)

        screen.fill(BG)
        _draw_header(screen, font_large, font_small, state, W, H, header_h)
        _draw_monitor_panel(screen, font_medium, font_small, state, W, H, header_h, left_w)
        _draw_event_panel(screen, font_medium, font_small, state, W, H, header_h, left_w, right_w)
        pygame.draw.line(screen, ACCENT, (left_w, header_h), (left_w, H), 1)

        with _lock:
            if _state["flash"] > 0:
                _state["flash"] -= 1

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


def _draw_header(screen, font_large, font_small, state, W, H, header_h):
    pygame.draw.rect(screen, PANEL, (0, 0, W, header_h))
    pygame.draw.line(screen, ACCENT, (0, header_h), (W, header_h), 1)

    title = font_large.render("MINI CORTEX", True, ACCENT)
    screen.blit(title, (16, header_h // 2 - title.get_height() // 2))

    now = time.strftime("%H:%M:%S")
    ts  = font_small.render(now, True, TEXT_SEC)
    screen.blit(ts, (W - ts.get_width() - 12, 6))

    env_parts = []
    if state["temp"]     is not None: env_parts.append(f"{state['temp']:.1f}°C")
    if state["pressure"] is not None: env_parts.append(f"{state['pressure']:.1f} hPa")
    if env_parts:
        env_surf = font_small.render("  |  ".join(env_parts), True, TEXT_SEC)
        screen.blit(env_surf, (W - env_surf.get_width() - 12,
                                header_h - env_surf.get_height() - 4))


def _draw_monitor_panel(screen, font_medium, font_small, state, W, H, header_h, left_w):
    channels = state["channels"]
    max_val  = max(channels) if max(channels) > 0 else 1

    margin_l = 12
    margin_r = 8
    trig_h   = font_medium.get_height() + 6
    label_h  = font_small.get_height() + 6
    tick_h   = 6

    panel_top    = header_h + 8
    panel_bottom = H - trig_h - label_h - tick_h - 4
    bar_max_h    = max(1, panel_bottom - panel_top)

    usable_w = left_w - margin_l - margin_r
    n        = 18
    slot_w   = usable_w // n
    bar_w    = max(slot_w - 3, 4)

    for i, val in enumerate(channels):
        x     = margin_l + i * slot_w
        bar_h = int((val / max_val) * bar_max_h)
        bar_h = max(0, min(bar_h, bar_max_h))

        pygame.draw.rect(screen, BAR_BG, (x, panel_top, bar_w, bar_max_h))

        color = BAR_COL
        if bar_h > 0:
            pygame.draw.rect(screen, color,
                             (x, panel_top + bar_max_h - bar_h, bar_w, bar_h))

        if val > 0:
            val_surf = font_small.render(str(int(val)), True, TEXT_PRI)
            val_x    = x + bar_w // 2 - val_surf.get_width() // 2
            val_y    = max(panel_top, panel_top + bar_max_h - bar_h - val_surf.get_height())
            screen.blit(val_surf, (val_x, val_y))

        tick_x = x + bar_w // 2
        pygame.draw.line(screen, TEXT_SEC,
                         (tick_x, panel_bottom + 2), (tick_x, panel_bottom + tick_h), 1)
        if i % 3 == 0:
            lbl   = font_small.render(str(i), True, TEXT_SEC)
            lbl_x = x + bar_w // 2 - lbl.get_width() // 2
            screen.blit(lbl, (lbl_x, panel_bottom + tick_h + 2))

    trig_surf = font_medium.render(f"Trig rate: {state['trig_rate']}", True, WARN)
    screen.blit(trig_surf, (margin_l, H - trig_h - 2))


def _draw_layer_grid(screen, font_small, bits9, ox, oy, cell, gap, flash_on, label):
    hit_col  = ALERT if flash_on else ACCENT
    miss_col = BAR_BG
    border   = (50, 70, 90)

    for bit_idx in range(9):
        col = bit_idx % 3
        row = 2 - (bit_idx // 3)
        x   = ox + col * (cell + gap)
        y   = oy + row * (cell + gap)
        hit = bits9[bit_idx] == '1'
        pygame.draw.rect(screen, hit_col if hit else miss_col, (x, y, cell, cell))
        pygame.draw.rect(screen, border, (x, y, cell, cell), 1)

    grid_w = 3 * cell + 2 * gap
    lbl    = font_small.render(label, True, TEXT_SEC)
    screen.blit(lbl, (ox + grid_w // 2 - lbl.get_width() // 2,
                       oy + 3 * (cell + gap) + 3))


def _draw_event_panel(screen, font_medium, font_small, state, W, H, header_h, left_w, right_w):
    mid_x    = left_w + right_w // 2
    flash_on = state["flash"] > 0

    if flash_on:
        flash_surf = pygame.Surface((right_w, H - header_h), pygame.SRCALPHA)
        flash_surf.fill((60, 10, 10, 100))
        screen.blit(flash_surf, (left_w, header_h))

    if state["event_word"] is None:
        waiting = font_medium.render("No event yet", True, TEXT_SEC)
        screen.blit(waiting, (mid_x - waiting.get_width() // 2, H // 2 - 10))
        return

    word   = state["event_word"]
    bits27 = f"{word & 0x7FFFFFF:027b}"

    lbl_h    = font_small.get_height() + 4
    foot_h   = font_medium.get_height() + 8
    avail_w  = right_w - 24
    avail_h  = H - header_h - foot_h - 16

    grid_pad = max(4, avail_h // 30)
    gap      = 2
    cell     = max(6, (avail_h - 3 * lbl_h - 2 * grid_pad) // 9)
    cell     = min(cell, max(6, (avail_w - 2 * gap) // 3))
    gap      = max(2, cell // 6)
    grid_pad = max(4, (avail_h - 3 * (3 * cell + 2 * gap) - 3 * lbl_h) // 2)

    grid_w     = 3 * cell + 2 * gap
    grid_h     = 3 * cell + 2 * gap
    total_h    = 3 * grid_h + 2 * grid_pad + 3 * lbl_h
    ox0        = left_w + (right_w - grid_w) // 2
    oy_top     = header_h + max(12, (avail_h - total_h) // 2) + 8

    for layer in range(2, -1, -1):
        slot  = 2 - layer
        oy    = oy_top + slot * (grid_h + lbl_h + grid_pad)
        bits9 = bits27[layer * 9 : layer * 9 + 9]
        _draw_layer_grid(screen, font_small, bits9, ox0, oy, cell, gap,
                         flash_on, f"z={layer}")

    for slot in range(2):
        y1    = oy_top + (slot + 1) * (grid_h + lbl_h + grid_pad) - grid_pad // 2
        x_mid = ox0 + grid_w // 2
        pygame.draw.line(screen, (40, 55, 75),
                         (x_mid, y1 - grid_pad // 2 + 2),
                         (x_mid, y1 + grid_pad // 2 - 2), 1)

    y_foot = H - foot_h
    if state["event_time"]:
        ts_surf = font_small.render(state["event_time"], True, TEXT_SEC)
        screen.blit(ts_surf, (left_w + 8, y_foot))
    cnt_surf = font_medium.render(f"Events: {state['event_count']}", True, TEXT_SEC)
    screen.blit(cnt_surf, (left_w + right_w - cnt_surf.get_width() - 10, y_foot))