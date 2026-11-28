#!/usr/bin/env python3
"""Transform an Aether checkout into a standalone《多娜多娜》iOS app."""
import argparse
from pathlib import Path
import re
import shutil


APP_NAME = "多娜多娜"
BUNDLE_ID = "com.dohna.aether.ios"
IPA_PREFIX = "DohnaDohna"
DOHNA_ICONS_DIR = Path(__file__).resolve().parent / "icons"
DOHNA_ICON_SIZES = (20, 29, 40, 58, 60, 76, 80, 87, 114, 120, 128, 136, 152, 167, 180, 192, 1024)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected 1 occurrence of anchor, found {count}")
    return text.replace(old, new, 1)


def patch_project_godot(aether_dir: Path) -> None:
    path = aether_dir / "apps/godot_app/project.godot"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, 'config/name="Aether"', f'config/name="{APP_NAME}"', "project.godot config/name")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_export_presets(aether_dir: Path) -> None:
    path = aether_dir / "apps/godot_app/export_presets.cfg"
    text = path.read_text(encoding="utf-8")
    for old_id in (
        'application/bundle_identifier="com.liuyu.aether.aether"',
        'application/bundle_identifier="com.liuyu.aetherkiri.kr37s"',
    ):
        text = text.replace(old_id, f'application/bundle_identifier="{BUNDLE_ID}"')
    if f'application/bundle_identifier="{BUNDLE_ID}"' not in text:
        raise ValueError("export_presets.cfg: bundle_identifier was not updated")
    text = text.replace(
        "Aether uses the microphone for in-game audio input when a game requests it.",
        "多娜多娜 uses the microphone only when a script requests audio input.",
    )
    text = text.replace(
        "Aether uses the photo you select as a game cover.",
        "多娜多娜 uses selected photos only for optional cover customization.",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_stage_ios_game_import(aether_dir: Path) -> None:
    path = aether_dir / "tools/stage_ios_game_import.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '"CFBundleDisplayName": "Send to Aether Visual Novels"',
        '"CFBundleDisplayName": "发送到多娜多娜"',
        "stage_ios_game_import CFBundleDisplayName",
    )
    text = replace_once(
        text,
        '"NSUbiquitousContainerName": "aether"',
        '"NSUbiquitousContainerName": "dohna"',
        "stage_ios_game_import NSUbiquitousContainerName",
    )
    path.write_text(text, encoding="utf-8", newline="\n")

    import_dir = aether_dir / "bridge/ios_game_import"
    for p in import_dir.glob("*.lproj/*.strings"):
        s = p.read_text(encoding="utf-8")
        s = s.replace("Send to Aether Visual Novels", f"发送到{APP_NAME}")
        s = s.replace("Aether Visual Novels", APP_NAME)
        s = s.replace("Aether 视觉小说目录", APP_NAME)
        s = s.replace("Aether", APP_NAME)
        p.write_text(s, encoding="utf-8", newline="\n")


def patch_build_ios_sh(aether_dir: Path) -> None:
    path = aether_dir / "scripts/build_ios.sh"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '        bluetooth_purpose="Aether uses Bluetooth to connect game controllers that you choose to use."',
        '        bluetooth_purpose="多娜多娜 uses Bluetooth for optional game controllers."'
        '\n        /usr/libexec/PlistBuddy -c \'Set :CFBundleDisplayName 多娜多娜\' "$info_plist" 2>/dev/null || \\'
        '\n            /usr/libexec/PlistBuddy -c \'Add :CFBundleDisplayName string 多娜多娜\' "$info_plist"'
        '\n        /usr/libexec/PlistBuddy -c \'Set :CFBundleName 多娜多娜\' "$info_plist" 2>/dev/null || \\'
        '\n            /usr/libexec/PlistBuddy -c \'Add :CFBundleName string 多娜多娜\' "$info_plist"',
        "build_ios.sh CFBundleDisplayName",
    )
    old_pkg = (
        '    rm -rf "$export_dir/Payload/Aether.app" "$export_dir/Aether-${config_cap}-Unsigned.ipa"\n'
        '    # Rename within the export volume instead of duplicating a multi-GB app.\n'
        '    mv "$export_dir/build/Aether.app" "$export_dir/Payload/"\n'
        '    if ! (cd "$export_dir" && zip -qry "Aether-${config_cap}-Unsigned.ipa" Payload); then\n'
        '        mv "$export_dir/Payload/Aether.app" "$export_dir/build/"\n'
        '        rm -f "$export_dir/Aether-${config_cap}-Unsigned.ipa"\n'
        '        return 1\n'
        '    fi\n'
        '    rm -rf "$export_dir/Payload" "$export_dir/build"\n'
        '    echo "Unsigned IPA created: $export_dir/Aether-${config_cap}-Unsigned.ipa"'
    )
    new_pkg = (
        f'    local ipa_name="{IPA_PREFIX}-${{config_cap}}-Unsigned.ipa"\n'
        '    python3 - "$export_dir/build/Aether.app" <<\'PY\'\n'
        'import plistlib, sys\n'
        'from pathlib import Path\n'
        'app = Path(sys.argv[1])\n'
        'assert (app / "Assets.car").is_file(), f"Missing Assets.car in {app}"\n'
        'leftover_aether = sorted(p.name for p in app.glob("AetherAppIcon*"))\n'
        'assert not leftover_aether, f"Unexpected Aether icon assets remain: {leftover_aether}"\n'
        'dohna_icons = sorted(p.name for p in app.glob("AppIcon*.png"))\n'
        'assert dohna_icons, f"Expected compiled AppIcon*.png files in {app}"\n'
        'info_p = app / "Info.plist"\n'
        'if info_p.is_file():\n'
        '    info = plistlib.loads(info_p.read_bytes())\n'
        '    info["CFBundleDisplayName"] = "多娜多娜"\n'
        '    info["CFBundleName"] = "多娜多娜"\n'
        '    for ikey in ("CFBundleIcons", "CFBundleIcons~ipad"):\n'
        '        if isinstance(info.get(ikey), dict):\n'
        '            info[ikey].pop("CFBundleAlternateIcons", None)\n'
        '    info_p.write_bytes(plistlib.dumps(info, sort_keys=False))\n'
        '    print("AppIcon PNGs:", dohna_icons)\n'
        '    print("CFBundleIcons:", info.get("CFBundleIcons"))\n'
        'for loc in app.glob("*.lproj/InfoPlist.strings"):\n'
        '    loc.write_bytes(plistlib.dumps({"CFBundleDisplayName": "多娜多娜", "CFBundleName": "多娜多娜"}, fmt=plistlib.FMT_BINARY))\n'
        'PY\n'
        '    rm -rf "$export_dir/Payload/Aether.app" "$export_dir/Aether-${config_cap}-Unsigned.ipa" "$export_dir/$ipa_name"\n'
        '    # Rename within the export volume instead of duplicating a multi-GB app.\n'
        '    mv "$export_dir/build/Aether.app" "$export_dir/Payload/"\n'
        '    if ! (cd "$export_dir" && zip -qry "$ipa_name" Payload); then\n'
        '        mv "$export_dir/Payload/Aether.app" "$export_dir/build/"\n'
        '        rm -f "$export_dir/$ipa_name"\n'
        '        return 1\n'
        '    fi\n'
        '    rm -rf "$export_dir/Payload" "$export_dir/build"\n'
        '    echo "Unsigned IPA created: $export_dir/$ipa_name"'
    )
    text = replace_once(text, old_pkg, new_pkg, "build_ios.sh package_ios_unsigned_ipa")
    old_export = (
        '    "$GODOT_BIN" --headless --recovery-mode --path "$GODOT_APP_DIR" \\\n'
        '        "$EXPORT_MODE" "$EXPORT_PRESET" "$PROJECT_ROOT/out/godot/ios/$BUILD_TYPE_LOWER/Aether.xcodeproj"'
    )
    new_export = (
        '    local export_log\n'
        '    export_log="$(mktemp /tmp/aether-godot-export.XXXXXX)"\n'
        '    "$GODOT_BIN" --headless --recovery-mode --path "$GODOT_APP_DIR" \\\n'
        '        "$EXPORT_MODE" "$EXPORT_PRESET" "$PROJECT_ROOT/out/godot/ios/$BUILD_TYPE_LOWER/Aether.xcodeproj" 2>&1 | tee "$export_log"\n'
        '    if grep -Eq \'SCRIPT ERROR:|Parse Error:|Failed to load script\' "$export_log"; then\n'
        '        echo "Error: Godot script parse error detected during iOS export!" >&2\n'
        '        rm -f "$export_log"\n'
        '        return 1\n'
        '    fi\n'
        '    rm -f "$export_log"'
    )
    text = replace_once(text, old_export, new_export, "build_ios.sh godot export script gate")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_builtin_demo(aether_dir: Path) -> None:
    path = aether_dir / "apps/godot_app/scripts/builtin_demo.gd"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "func ensure_installed() -> Dictionary:\n",
        "func ensure_installed() -> Dictionary:\n"
        "    if OS.get_name() == \"iOS\":\n"
        "        return {}\n",
        "builtin_demo ensure_installed",
    )
    text = replace_once(
        text,
        "func reconcile_games(games: Array[Dictionary]) -> Array[Dictionary]:\n",
        "func reconcile_games(games: Array[Dictionary]) -> Array[Dictionary]:\n"
        "    if OS.get_name() == \"iOS\":\n"
        "        var kept: Array[Dictionary] = []\n"
        "        for g in games:\n"
        "            if not is_game(g):\n"
        "                kept.append(g)\n"
        "        return kept\n",
        "builtin_demo reconcile_games",
    )
    assert "\t" not in text, "builtin_demo.gd must use spaces only"
    path.write_text(text, encoding="utf-8", newline="\n")


DOHNA_STANDALONE_METHODS = '''
var dohna_setup_layer: CanvasLayer = null
var dohna_status_label: Label = null

func _dohna_is_standalone_ios() -> bool:
    return OS.get_name() == "iOS"

func _dohna_dir_has_game(dir_path: String) -> bool:
    if dir_path.is_empty() or not DirAccess.dir_exists_absolute(dir_path):
        return false
    var d := DirAccess.open(dir_path)
    if d == null:
        return false
    var has_ain := false
    var has_ini := false
    for f in d.get_files():
        if d.is_link(f):
            continue
        var lower := String(f).to_lower()
        if lower == "dohnadohna.ain":
            has_ain = true
        elif lower == "alicestart.ini" or lower == "system40.ini":
            has_ini = true
    return has_ain and has_ini

func _dohna_find_game_root() -> String:
    var user_root := ProjectSettings.globalize_path("user://").simplify_path().trim_suffix("/")
    if _dohna_dir_has_game(user_root):
        return user_root
    var skip_names := [
        "games", "savedata", "cache", "runtime_fonts", "preferences",
        "builtin_games", "aether_fonts", "inbox"
    ]
    var preferred_dirs: Array[String] = []
    var root_dir := DirAccess.open(user_root)
    if root_dir != null:
        var subdirs := Array(root_dir.get_directories())
        subdirs.sort()
        for sub_raw in subdirs:
            var sub := String(sub_raw)
            if sub.begins_with(".") or root_dir.is_link(sub):
                continue
            if sub.to_lower() in skip_names:
                continue
            var candidate := user_root.path_join(sub)
            if sub.to_lower().find("dohna") >= 0 or sub.find("多娜") >= 0:
                preferred_dirs.push_front(candidate)
            else:
                preferred_dirs.append(candidate)
    for candidate in preferred_dirs:
        if _dohna_dir_has_game(candidate):
            return candidate
    var games_root := ProjectSettings.globalize_path("user://Games").simplify_path().trim_suffix("/")
    var games_dir := DirAccess.open(games_root)
    if games_dir != null:
        var gsubs := Array(games_dir.get_directories())
        gsubs.sort()
        for sub_raw in gsubs:
            var sub := String(sub_raw)
            if sub.begins_with(".") or games_dir.is_link(sub):
                continue
            var candidate := games_root.path_join(sub)
            if _dohna_dir_has_game(candidate):
                return candidate
    for candidate in preferred_dirs:
        var outer_dir := DirAccess.open(candidate)
        if outer_dir == null:
            continue
        for inner_raw in outer_dir.get_directories():
            var inner := String(inner_raw)
            if inner.begins_with(".") or outer_dir.is_link(inner):
                continue
            if inner.to_lower() in ["data", "movie", "savedata", "manual", "license"]:
                continue
            var nested := candidate.path_join(inner)
            if _dohna_dir_has_game(nested):
                return nested
    return ""

func _dohna_ensure_xsys4rc(root: String) -> void:
    var rc_path := root.path_join(".xsys4rc")
    if FileAccess.file_exists(rc_path):
        return
    var f := FileAccess.open(rc_path, FileAccess.WRITE)
    if f != null:
        f.store_string("encoding = \\"gbk\\"\\n")
        f.flush()

func _dohna_copy_missing_or_newer(src_dir: String, dst_dir: String, overwrite_newer: bool) -> void:
    if not DirAccess.dir_exists_absolute(src_dir):
        return
    DirAccess.make_dir_recursive_absolute(dst_dir)
    var d := DirAccess.open(src_dir)
    if d == null:
        return
    for file_raw in d.get_files():
        var fname := String(file_raw)
        if fname.begins_with(".") or d.is_link(fname):
            continue
        var src_file := src_dir.path_join(fname)
        var dst_file := dst_dir.path_join(fname)
        if not FileAccess.file_exists(dst_file):
            DirAccess.copy_absolute(src_file, dst_file)
        elif overwrite_newer:
            var src_mtime := FileAccess.get_modified_time(src_file)
            var dst_mtime := FileAccess.get_modified_time(dst_file)
            var src_size := FileAccess.get_size(src_file)
            var dst_size := FileAccess.get_size(dst_file)
            if src_mtime > dst_mtime or src_size != dst_size:
                DirAccess.copy_absolute(src_file, dst_file)

func _dohna_sync_savedata(root: String) -> void:
    var save_locs = preload("res://scripts/game_save_locations.gd")
    var identity: String = save_locs._script_identity(root, "xsystem4")
    if identity.is_empty():
        return
    var target := root.path_join("savedata/xsystem4").path_join(identity)
    DirAccess.make_dir_recursive_absolute(target)
    var user_root := ProjectSettings.globalize_path("user://").simplify_path().trim_suffix("/")
    var save_sources: Array[String] = [root.path_join("SaveData"), root.path_join("savedata")]
    if user_root != root:
        save_sources.append(user_root.path_join("SaveData"))
    for src in save_sources:
        if src == target:
            continue
        _dohna_copy_missing_or_newer(src, target, false)
        _dohna_copy_missing_or_newer(src.path_join("User"), target.path_join("User"), true)
    if user_root != root:
        _dohna_copy_missing_or_newer(user_root.path_join("User"), target.path_join("User"), true)

func _dohna_hide_setup_overlay() -> void:
    if dohna_setup_layer != null and is_instance_valid(dohna_setup_layer):
        dohna_setup_layer.visible = false

func _dohna_show_setup_overlay(detail_text: String = "") -> void:
    if shell_root != null:
        shell_root.visible = false
    if dohna_setup_layer == null or not is_instance_valid(dohna_setup_layer):
        dohna_setup_layer = CanvasLayer.new()
        dohna_setup_layer.name = "DohnaStandaloneSetup"
        dohna_setup_layer.layer = 50
        add_child(dohna_setup_layer)

        var backdrop := ColorRect.new()
        backdrop.set_anchors_preset(Control.PRESET_FULL_RECT)
        backdrop.color = Color(0.06, 0.06, 0.08, 1.0)
        dohna_setup_layer.add_child(backdrop)

        var center := CenterContainer.new()
        center.set_anchors_preset(Control.PRESET_FULL_RECT)
        dohna_setup_layer.add_child(center)

        var card := PanelContainer.new()
        var safe_w := _ui_safe_rect(get_viewport_rect().size).size.x
        card.custom_minimum_size = Vector2(minf(520.0, maxf(260.0, safe_w - 36.0)), 0)
        card.add_theme_stylebox_override("panel", _dialog_style())
        center.add_child(card)

        var margin := MarginContainer.new()
        margin.add_theme_constant_override("margin_left", 28)
        margin.add_theme_constant_override("margin_top", 26)
        margin.add_theme_constant_override("margin_right", 28)
        margin.add_theme_constant_override("margin_bottom", 26)
        card.add_child(margin)

        var vbox := VBoxContainer.new()
        vbox.add_theme_constant_override("separation", 14)
        margin.add_child(vbox)

        var title := Label.new()
        title.text = "多娜多娜 · 一起来干坏事吧"
        title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
        title.add_theme_font_size_override("font_size", 24)
        title.add_theme_color_override("font_color", ui_tokens.text_primary)
        vbox.add_child(title)

        dohna_status_label = Label.new()
        dohna_status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
        dohna_status_label.add_theme_font_size_override("font_size", 15)
        dohna_status_label.add_theme_color_override("font_color", ui_tokens.text_secondary)
        vbox.add_child(dohna_status_label)

        var row := HBoxContainer.new()
        row.add_theme_constant_override("separation", 12)
        vbox.add_child(row)

        var retry_btn := _pill_button("重新检测并启动")
        retry_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
        retry_btn.custom_minimum_size = Vector2(180, 48)
        retry_btn.pressed.connect(func(): _dohna_standalone_boot())
        row.add_child(retry_btn)

        var mgr_btn := _secondary_dialog_button("打开原管理界面", Vector2(170, 48))
        mgr_btn.pressed.connect(func():
            _dohna_hide_setup_overlay()
            if shell_root != null:
                shell_root.visible = true
            _show_home()
        )
        row.add_child(mgr_btn)

    dohna_status_label.text = detail_text if not detail_text.is_empty() else _dohna_missing_help_text()
    dohna_setup_layer.visible = true
    dohna_setup_layer.move_to_front()

func _dohna_missing_help_text() -> String:
    var user_root := ProjectSettings.globalize_path("user://").simplify_path().trim_suffix("/")
    var found_items: Array[String] = []
    var d := DirAccess.open(user_root)
    if d != null:
        for name_raw in Array(d.get_directories()) + Array(d.get_files()):
            var n := String(name_raw)
            if not n.begins_with(".") and n.to_lower() != "games":
                found_items.append(n)
    var preview := "空" if found_items.is_empty() else ", ".join(PackedStringArray(found_items.slice(0, 6)))
    return (
        "未检测到《多娜多娜》游戏文件。\\n\\n"
        + "请将准备好的 DohnaDohna 游戏文件夹（含 dohnadohna.ain、AliceStart.ini、.afa 数据等）"
        + "通过电脑文件共享或 iPhone「文件」App 复制到：\\n"
        + "我的 iPhone > 多娜多娜\\n\\n"
        + "若自带存档和捏人，请确保 SaveData 与 User 文件夹在游戏目录内。\\n"
        + "当前目录项目：" + preview
    )

func _dohna_standalone_boot() -> void:
    if not _dohna_is_standalone_ios():
        return
    if game_running:
        return
    var root := _dohna_find_game_root()
    if root.is_empty():
        _dohna_show_setup_overlay()
        return
    _dohna_hide_setup_overlay()
    _dohna_ensure_xsys4rc(root)
    _dohna_sync_savedata(root)
    var game := _game_info_from_path(root)
    game["engine"] = RUNTIME_XSYSTEM4
    if String(game.get("title", "")).is_empty():
        game["title"] = APP_DISPLAY_NAME
    selected_game = game
    if shell_root != null:
        shell_root.visible = false
    _start_selected_game_after_iap()
'''


def patch_main_gd(aether_dir: Path) -> None:
    path = aether_dir / "apps/godot_app/scripts/main.gd"
    text = path.read_text(encoding="utf-8")

    text = replace_once(
        text,
        'const APP_DISPLAY_NAME := "Aether"',
        f'const APP_DISPLAY_NAME := "{APP_NAME}"',
        "main.gd APP_DISPLAY_NAME",
    )

    # 1. Never pop Aether legal/store modals on iOS standalone build.
    text = replace_once(
        text,
        "func _ios_statement_required(platform_name: String = \"\") -> bool:\n",
        "func _ios_statement_required(platform_name: String = \"\") -> bool:\n"
        "    if _dohna_is_standalone_ios():\n"
        "        return false\n",
        "main.gd _ios_statement_required",
    )
    text = replace_once(
        text,
        "func _legal_agreement_required() -> bool:\n",
        "func _legal_agreement_required() -> bool:\n"
        "    if _dohna_is_standalone_ios():\n"
        "        return false\n",
        "main.gd _legal_agreement_required",
    )

    # 2. Hide Aether main shell immediately in _build_ui so it never flashes on iOS.
    text = replace_once(
        text,
        "    _build_loading_panel()\n    _fit_full_rects()\n",
        "    _build_loading_panel()\n"
        "    _fit_full_rects()\n"
        "    if _dohna_is_standalone_ios() and shell_root != null:\n"
        "        shell_root.visible = false\n",
        "main.gd _build_ui hide shell_root",
    )

    # 3. Skip Aether's update checks and startup announcement modals in standalone mode.
    text = replace_once(
        text,
        "func _check_app_update_silently() -> void:\n",
        "func _check_app_update_silently() -> void:\n"
        "    if _dohna_is_standalone_ios():\n"
        "        return\n",
        "main.gd _check_app_update_silently",
    )
    text = replace_once(
        text,
        "func _maybe_show_notice() -> void:\n",
        "func _maybe_show_notice() -> void:\n"
        "    if _dohna_is_standalone_ios():\n"
        "        return\n",
        "main.gd _maybe_show_notice",
    )

    # 4. Boot straight into《多娜多娜》after ready!
    text = replace_once(
        text,
        "func _continue_ready_after_legal_gate() -> void:\n"
        "    if legal_gate_completed:\n"
        "        return\n"
        "    if _show_next_required_legal_document():\n"
        "        return\n"
        "    legal_gate_completed = true\n",
        "func _continue_ready_after_legal_gate() -> void:\n"
        "    if legal_gate_completed:\n"
        "        return\n"
        "    if _show_next_required_legal_document():\n"
        "        return\n"
        "    legal_gate_completed = true\n"
        "    if _dohna_is_standalone_ios():\n"
        "        call_deferred(\"_dohna_standalone_boot\")\n"
        "        return\n",
        "main.gd _continue_ready_after_legal_gate",
    )

    # 5. When exiting the game back, show standalone relaunch/setup overlay instead of Aether library.
    text = replace_once(
        text,
        "    if shell_root != null:\n"
        "        shell_root.visible = true\n"
        "    Input.mouse_mode = Input.MOUSE_MODE_VISIBLE\n"
        "    _show_home()\n"
        "    _fit_full_rects()\n"
        "    runtime_exit_cleanup_pending = false\n",
        "    Input.mouse_mode = Input.MOUSE_MODE_VISIBLE\n"
        "    _fit_full_rects()\n"
        "    if _dohna_is_standalone_ios():\n"
        "        if shell_root != null:\n"
        "            shell_root.visible = false\n"
        "        _dohna_show_setup_overlay(\"已退出《多娜多娜》，点击下方按钮可重新进入游戏。\")\n"
        "    else:\n"
        "        if shell_root != null:\n"
        "            shell_root.visible = true\n"
        "        _show_home()\n"
        "    runtime_exit_cleanup_pending = false\n",
        "main.gd _return_to_library_after_runtime_exit",
    )

    # 6. Append standalone helper methods cleanly at the end of main.gd.
    text = text.rstrip() + "\n" + DOHNA_STANDALONE_METHODS.lstrip("\n")

    assert "\t" not in text, "main.gd must not contain tabs (GDScript requires consistent 4-space indentation)"
    path.write_text(text, encoding="utf-8", newline="\n")


DOHNA_STAGE_IOS_ICONS_CODE = '''
def stage_dohna_ios_icons(project):
    import struct
    from stage_ios_game_import import app_target, configurations, read_project, write_project, write_plist

    data = read_project(project)
    objects = data["objects"]
    _, app = app_target(data)
    export = project.parent
    icons_src = ASSETS / "icons"

    appiconsets = sorted(export.rglob("*.appiconset"))
    if not appiconsets:
        raise FileNotFoundError(f"Expected Godot-exported AppIcon.appiconset under {export}")

    copied = 0
    for iconset in appiconsets:
        for png in sorted(iconset.glob("*.png")):
            raw = png.read_bytes()
            if raw[:8] != b"\\x89PNG\\r\\n\\x1a\\n":
                raise ValueError(f"Expected PNG header in {png}")
            w, h = struct.unpack(">II", raw[16:24])
            if w != h:
                raise ValueError(f"Expected square app icon in {png}, got {w}x{h}")
            candidate = icons_src / f"icon_{w}x{w}.png"
            if candidate.is_file():
                shutil.copyfile(candidate, png)
            else:
                master = icons_src / "app_store_1024x1024.png"
                subprocess.run(["sips", "-z", str(w), str(h), str(master), "--out", str(png)], check=True)
            copied += 1
    if copied == 0:
        raise RuntimeError(f"No PNG icon entries found inside {appiconsets}")

    for config in configurations(objects, app):
        settings = config["buildSettings"]
        settings["ASSETCATALOG_COMPILER_APPICON_NAME"] = "AppIcon"
        settings.pop("ASSETCATALOG_COMPILER_ALTERNATE_APPICON_NAMES", None)
        info_path = export / settings["INFOPLIST_FILE"].strip('"')
        if info_path.is_file():
            info = plistlib.loads(info_path.read_bytes())
            for key in ("CFBundleIcons", "CFBundleIcons~ipad"):
                if isinstance(info.get(key), dict):
                    info[key].pop("CFBundleAlternateIcons", None)
            write_plist(info_path, info)

    write_project(project, data)
    print(f"Staged {copied} Dohna Dohna app icon PNG(s) across {len(appiconsets)} appiconset(s)")
'''


def patch_app_icons(aether_dir: Path) -> None:
    if not DOHNA_ICONS_DIR.is_dir():
        raise FileNotFoundError(f"Dohna icon directory not found: {DOHNA_ICONS_DIR}")
    required = ["app_store_1024x1024.png", "icon.png", *(f"icon_{sz}x{sz}.png" for sz in DOHNA_ICON_SIZES)]
    for name in required:
        if not (DOHNA_ICONS_DIR / name).is_file():
            raise FileNotFoundError(f"Missing Dohna icon asset: {DOHNA_ICONS_DIR / name}")

    assets_dir = aether_dir / "apps/godot_app/assets"
    replaced = 0
    shutil.copyfile(DOHNA_ICONS_DIR / "icon.png", assets_dir / "icon.png")
    replaced += 1
    for folder in (assets_dir / "icons", assets_dir / "icons/astryx", assets_dir / "icons/astryx/dark"):
        for existing in sorted(folder.glob("*.png")):
            src = DOHNA_ICONS_DIR / existing.name
            if not src.is_file():
                raise FileNotFoundError(f"No Dohna replacement icon for {existing}")
            shutil.copyfile(src, existing)
            replaced += 1
    if replaced < 50:
        raise RuntimeError(f"Expected >= 50 replaced icon PNGs, only replaced {replaced}")

    app_icon_gd = aether_dir / "apps/godot_app/scripts/ui/app_icon.gd"
    gd_text = app_icon_gd.read_text(encoding="utf-8")
    gd_text = replace_once(
        gd_text,
        "static func apply(astryx: bool, dark: bool = false) -> void:\n",
        "static func apply(astryx: bool, dark: bool = false) -> void:\n"
        "    if OS.get_name() == \"iOS\":\n"
        "        return\n",
        "app_icon.gd apply iOS guard",
    )
    app_icon_gd.write_text(gd_text, encoding="utf-8", newline="\n")

    stage_icons_py = aether_dir / "tools/stage_app_icons.py"
    stage_text = stage_icons_py.read_text(encoding="utf-8")
    stage_text = replace_once(
        stage_text,
        "    stage_ios_icons(parser.parse_args().ios_project, liquid_glass=supports_icon_composer())",
        "    stage_dohna_ios_icons(parser.parse_args().ios_project)",
        "stage_app_icons.py main call",
    )
    stage_text = stage_text.replace(
        "if __name__ == \"__main__\":",
        DOHNA_STAGE_IOS_ICONS_CODE.lstrip("\n") + "\n\nif __name__ == \"__main__\":",
        1,
    )
    stage_icons_py.write_text(stage_text, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("aether_dir", type=Path)
    aether_dir = parser.parse_args().aether_dir.resolve()
    if not (aether_dir / "apps/godot_app/project.godot").is_file():
        raise FileNotFoundError(f"Invalid Aether directory: {aether_dir}")

    patch_project_godot(aether_dir)
    patch_app_icons(aether_dir)
    patch_export_presets(aether_dir)
    patch_stage_ios_game_import(aether_dir)
    patch_build_ios_sh(aether_dir)
    patch_builtin_demo(aether_dir)
    patch_main_gd(aether_dir)
    print(f"Applied standalone {APP_NAME} overlay cleanly in {aether_dir}")


if __name__ == "__main__":
    main()
