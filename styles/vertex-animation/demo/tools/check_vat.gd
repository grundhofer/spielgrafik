extends SceneTree
## Prüft die Vertex-Animation-Texturen in Godot (headless):
##   godot --headless --path styles/vertex-animation/demo --script res://tools/check_vat.gd -- <flag_ref.bin>
## 1. Format der importierten Texturen (erwartet RGBAH = Half Float, keine Kompression).
## 2. Fahne: Positionen aus Mesh (Ruhelage) + Textur rekonstruieren wie im Shader (Spalte aus UV2) und mit den
##    float32-Positionen aus Blender (assets/measure/flag_ref.bin, Bilder 0, 37, 119) vergleichen.
## 3. Möwe: jede Spalte muss genau einmal über UV2 erreicht werden.

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var ref_path: String = args[0] if args.size() > 0 else ""
	for p in ["res://vat/flag_pos.exr", "res://vat/flag_nrm.exr", "res://vat/gull_pos.exr", "res://vat/gull_nrm.exr"]:
		var tex := load(p) as Texture2D
		var img := tex.get_image()
		print("TEX %s %dx%d format=%d (RGBAH=%d) mipmaps=%s bytes=%d" % [p, img.get_width(), img.get_height(),
			img.get_format(), Image.FORMAT_RGBAH, img.has_mipmaps(), img.get_data().size()])
	for name in ["flag", "gull"]:
		var scene := (load("res://models/%s.glb" % name) as PackedScene).instantiate()
		var mi := scene.find_children("*", "MeshInstance3D", true, false)[0] as MeshInstance3D
		var arr := mi.mesh.surface_get_arrays(0)
		var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var uv2: PackedVector2Array = arr[Mesh.ARRAY_TEX_UV2]
		var img := (load("res://vat/%s_pos.exr" % name) as Texture2D).get_image()
		var w := img.get_width()
		var cols := {}
		for i in verts.size():
			cols[clampi(int(uv2[i].x * w), 0, w - 1)] = true
		print("MESH %s godot_vertices=%d texture_columns=%d columns_hit=%d shadow_mesh=%s" % [name, verts.size(), w,
			cols.size(), mi.mesh.shadow_mesh != null])
		if name == "flag" and ref_path != "":
			var f := FileAccess.open(ref_path, FileAccess.READ)
			var buf := f.get_buffer(f.get_length())
			var ref := buf.to_float32_array()
			var frames := [0, 37, 119]
			var max_err := 0.0
			var sum_err := 0.0
			var n := 0
			for k in frames.size():
				for i in verts.size():
					var col := clampi(int(uv2[i].x * w), 0, w - 1)
					var c := img.get_pixel(col, frames[k])
					var p := verts[i] + Vector3(c.r, c.g, c.b)
					var base := (k * w + col) * 3
					var r := Vector3(ref[base], ref[base + 1], ref[base + 2])
					var e := p.distance_to(r)
					max_err = maxf(max_err, e)
					sum_err += e
					n += 1
			print("FLAGCHECK frames=%s points=%d max_err_mm=%.3f mean_err_mm=%.3f" % [str(frames), n, max_err * 1000.0, sum_err / n * 1000.0])
		scene.free()
	quit()
