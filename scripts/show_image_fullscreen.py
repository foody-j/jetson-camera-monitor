#!/usr/bin/env python3
import argparse
import os
import sys

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt


def _maximize(fig) -> None:
    manager = plt.get_current_fig_manager()
    try:
        manager.full_screen_toggle()
        return
    except Exception:
        pass
    window = getattr(manager, "window", None)
    if window is None:
        return
    for fn_name, arg in (("state", "zoomed"), ("showMaximized", None), ("Maximize", None)):
        try:
            fn = getattr(window, fn_name)
        except Exception:
            continue
        try:
            if arg is None:
                fn()
            else:
                fn(arg)
            return
        except Exception:
            continue


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_path")
    parser.add_argument("--title", default="Vibration Plot")
    args = parser.parse_args()

    image_path = os.path.abspath(args.image_path)
    if not os.path.exists(image_path):
        print(f"[plot-viewer] missing file: {image_path}", file=sys.stderr)
        return 1

    img = mpimg.imread(image_path)
    fig = plt.figure(args.title, facecolor="black")
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.imshow(img)
    ax.axis("off")
    fig.canvas.manager.set_window_title(args.title)
    _maximize(fig)

    def _close(_event):
        plt.close(fig)

    fig.canvas.mpl_connect("key_press_event", lambda event: _close(event) if event.key in {"escape", "q"} else None)
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
