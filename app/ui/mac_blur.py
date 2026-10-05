"""macOS Native Frosted Glass / Vibrancy support via Cocoa NSVisualEffectView."""

import sys
import ctypes
from typing import Optional


def apply_mac_vibrancy(win_id: int, dark: bool = True) -> bool:
    """Inject NSVisualEffectView behind the window on macOS to provide true frosted glass blur."""
    if sys.platform != "darwin":
        return False

    try:
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.restype = ctypes.c_void_p

        # NSView from winId
        ns_view = ctypes.c_void_p(win_id)
        if not ns_view:
            return False

        # [ns_view window]
        sel_window = objc.sel_registerName(b"window")
        ns_window = objc.objc_msgSend(ns_view, sel_window)
        if not ns_window:
            return False

        # [ns_window contentView]
        sel_content_view = objc.sel_registerName(b"contentView")
        content_view = objc.objc_msgSend(ns_window, sel_content_view)
        if not content_view:
            return False

        # [[NSVisualEffectView alloc] init]
        cls_effect_view = objc.objc_getClass(b"NSVisualEffectView")
        sel_alloc = objc.sel_registerName(b"alloc")
        sel_init = objc.sel_registerName(b"init")
        effect_view = objc.objc_msgSend(cls_effect_view, sel_alloc)
        effect_view = objc.objc_msgSend(effect_view, sel_init)
        if not effect_view:
            return False

        # [effect_view setAutoresizingMask: 18] (NSViewWidthSizable | NSViewHeightSizable)
        sel_mask = objc.sel_registerName(b"setAutoresizingMask:")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        objc.objc_msgSend(effect_view, sel_mask, ctypes.c_ulong(18))

        # [effect_view setBlendingMode: 0] (NSVisualEffectBlendingModeBehindWindow)
        sel_blending = objc.sel_registerName(b"setBlendingMode:")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        objc.objc_msgSend(effect_view, sel_blending, ctypes.c_long(0))

        # [effect_view setState: 1] (NSVisualEffectStateActive)
        sel_state = objc.sel_registerName(b"setState:")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        objc.objc_msgSend(effect_view, sel_state, ctypes.c_long(1))

        # [effect_view setMaterial: dark ? 2 : 1] (2 = NSVisualEffectMaterialDark, 1 = Light)
        sel_material = objc.sel_registerName(b"setMaterial:")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        # material 2: Dark HUD, 1: Light
        objc.objc_msgSend(effect_view, sel_material, ctypes.c_long(2 if dark else 1))

        # [content_view addSubview:effect_view positioned:-1 relativeTo:nil] (-1 = NSWindowBelow)
        sel_add_subview = objc.sel_registerName(b"addSubview:positioned:relativeTo:")
        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_long,
            ctypes.c_void_p,
        ]
        objc.objc_msgSend(content_view, sel_add_subview, effect_view, ctypes.c_long(-1), ctypes.c_void_p(0))
        return True
    except Exception:
        return False
