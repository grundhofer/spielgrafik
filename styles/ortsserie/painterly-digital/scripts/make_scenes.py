#!/usr/bin/env python3
"""Schreibt die drei Godot-Szenen styles/ortsserie/demo/painterly-digital/<ort>.tscn (Text, von Hand lesbar).

    .venv/bin/python -I styles/ortsserie/painterly-digital/scripts/make_scenes.py

Jede Szene: Wurzel Control 1280x720 mit ort.gd, darin TextureRect „Bild“ (Standbild) mit dem Kinemagramm-Shader
und den Masken des Orts; die Textleiste baut ort.gd. Nur res://painterly-digital/-Pfade.
"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DEMO = ROOT / "styles" / "ortsserie" / "demo" / "painterly-digital"

ORTE = {
    "leuchtturm": ("Leuchtturm", "Im Leuchtturm",
                   "Die große Linse glimmt und dreht sich.\nDraußen versinkt der Abend im Meer."),
    "stube": ("Stube", "Stube des Hafenmeisters",
              "Im Kamin knistert die Glut, die Kerze flackert.\nAuf dem Tisch liegt eine Seekarte."),
    "klippe": ("Klippe", "Klippenpfad",
               "Der Wind streicht durch Gras und Heide.\nTief unten leuchten die Fenster des Hafens."),
}

TEMPLATE = """[gd_scene load_steps=10 format=3]

[ext_resource type="Script" path="res://painterly-digital/ort.gd" id="1_ort"]
[ext_resource type="Shader" path="res://painterly-digital/shaders/ort.gdshader" id="2_shader"]
[ext_resource type="Texture2D" path="res://painterly-digital/art/{ort}/still.png" id="3_still"]
[ext_resource type="Texture2D" path="res://painterly-digital/art/{ort}/plate.png" id="4_plate"]
[ext_resource type="Texture2D" path="res://painterly-digital/art/{ort}/mask_a.png" id="5_ma"]
[ext_resource type="Texture2D" path="res://painterly-digital/art/{ort}/mask_b.png" id="6_mb"]
[ext_resource type="Texture2D" path="res://painterly-digital/art/{ort}/mask_c.png" id="7_mc"]
[ext_resource type="Texture2D" path="res://painterly-digital/art/noise.png" id="8_noise"]

[sub_resource type="ShaderMaterial" id="M_ort"]
shader = ExtResource("2_shader")
shader_parameter/plate = ExtResource("4_plate")
shader_parameter/mask_a = ExtResource("5_ma")
shader_parameter/mask_b = ExtResource("6_mb")
shader_parameter/mask_c = ExtResource("7_mc")
shader_parameter/noise_tex = ExtResource("8_noise")

[node name="{node}" type="Control"]
clip_contents = true
layout_mode = 3
anchors_preset = 0
offset_right = 1280.0
offset_bottom = 720.0
mouse_filter = 2
script = ExtResource("1_ort")
ort = "{ort}"
title = "{title}"
line = "{line}"

[node name="Bild" type="TextureRect" parent="."]
material = SubResource("M_ort")
layout_mode = 0
offset_right = 1280.0
offset_bottom = 720.0
mouse_filter = 2
texture = ExtResource("3_still")
expand_mode = 1
"""


def main():
    for ort, (node, title, line) in ORTE.items():
        text = TEMPLATE.format(ort=ort, node=node, title=title, line=line.replace("\n", "\\n"))
        (DEMO / f"{ort}.tscn").write_text(text)
        print(DEMO.relative_to(ROOT) / f"{ort}.tscn")


if __name__ == "__main__":
    main()
