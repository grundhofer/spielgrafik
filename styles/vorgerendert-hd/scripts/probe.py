"""Rendered checks: deterministic animation, planted feet, depth, shadow catcher and renderer comparison.
Run with the project venv. Raw frames stay in a unique temporary directory and are removed after measurement.
"""
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

STYLE = Path(__file__).resolve().parent.parent
RESULT = STYLE / 'assets/probe.json'


def read(path):
    return np.asarray(Image.open(path).convert('RGB'), dtype=np.int16)


def main():
    result = {'errors': [], 'warnings': []}
    with tempfile.TemporaryDirectory(prefix='spielgrafik-hd-') as temporary:
        scratch = Path(temporary)

        def run(name, args, count=2, renderer='forward_plus'):
            folder = scratch / name
            folder.mkdir()
            cmd = ['godot', '--path', str(STYLE / 'demo'), '--position', '20000,20000',
                   '--rendering-method', renderer, '--write-movie', str(folder / 'f.png'),
                   '--fixed-fps', '30', '--quit-after', str(count), '--', *args]
            process = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            log = process.stdout + process.stderr
            result['errors'] += [name + ': ' + line for line in log.splitlines() if re.search(r'\bERROR\b', line)]
            result['warnings'] += [name + ': ' + line for line in log.splitlines() if re.search(r'\bWARNING\b', line)]
            files = sorted(folder.glob('f*.png'))
            assert process.returncode == 0 and len(files) == count, (name, log[-1000:])
            return files, log

        key, log = run('key', ['--key', '--feet-log'], 180)
        nod, _ = run('no-depth', ['--key', '--no-depth'], 180)
        repeat, _ = run('repeat', ['--key'], 180)
        result['identical_runs'] = all(hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()
                                       for a, b in zip(key, repeat))
        masks = []
        occlusion = []
        standing_rows = []
        for i, (a, b) in enumerate(zip(key, nod)):
            active, full = read(a), read(b)
            background = full[0, 0]
            visible = np.max(np.abs(active - background), axis=2) > 3
            complete = np.max(np.abs(full - background), axis=2) > 3
            masks.append(complete)
            if complete.any():
                occlusion.append(float((complete & ~visible).sum() / complete.sum()))
                if i >= 120:
                    standing_rows.append(int(np.where(complete)[0].max()))
        result['occlusion_max_share'] = round(max(occlusion), 4)
        result['standing_foot_rows'] = sorted(set(standing_rows))
        feet = []
        for line in log.splitlines():
            if line.startswith('FEET '):
                t = float(re.search(r't=([\d.]+)', line).group(1))
                matches = re.findall(r'(foot\.[LR])=\(([-\d.]+),([-\d.]+),([-\d.]+)\)\|\(([-\d.]+),([-\d.]+)\)', line)
                feet.append((t, {bone: np.array(list(map(float, values))) for bone, *values in matches}))
        steps = []
        for (ta, a), (tb, b) in zip(feet, feet[1:]):
            if not (tb < 3.7 and not (ta < 2.1 <= tb)):
                continue
            for bone in ['foot.L', 'foot.R']:
                if a[bone][1] < 0.025 and b[bone][1] < 0.025:
                    steps.append(float(np.linalg.norm(b[bone][3:] - a[bone][3:])))
        result['planted_foot_screen_step_px'] = {key: round(float(value), 3) for key, value in
            zip(['median', 'p90', 'max'], [np.median(steps), np.percentile(steps, 90), max(steps)])}

        normal, _ = run('normal', ['--at=4.9', '--no-ui'])
        no_shadow, _ = run('no-catcher', ['--at=4.9', '--no-ui', '--no-catcher'])
        no_panorama, _ = run('no-panorama', ['--at=4.9', '--no-ui', '--no-panorama'])
        base = read(normal[-1])
        diff = np.abs(base - read(no_shadow[-1])).max(axis=2)
        result['catcher_pixels_changed_gt3'] = int((diff > 3).sum())
        result['catcher_max_difference'] = int(diff.max())
        signed = (read(no_shadow[-1]) - base).mean(axis=2)
        result['catcher_darkened_pixels_gt3'] = int((signed > 3).sum())
        result['catcher_lightened_pixels_gt3'] = int((signed < -3).sum())
        crop = Image.fromarray(np.clip(diff * 4, 0, 255).astype(np.uint8))
        crop.save(STYLE / 'assets/preview/catcher_difference.png')
        result['panorama_pixels_changed_gt3'] = int((np.abs(base - read(no_panorama[-1])).max(axis=2) > 3).sum())
        empty, _ = run('empty', ['--at=4.9', '--only-bg', '--no-anim', '--no-ui'])
        empty_no_shadow, _ = run('empty-no-catcher', ['--at=4.9', '--only-bg', '--no-anim', '--no-ui', '--no-catcher'])
        result['catcher_without_character_max_difference'] = int(np.abs(read(empty[-1]) - read(empty_no_shadow[-1])).max())
        expected = read(STYLE / 'assets/preview/nah.png')
        result['blender_preview_vs_godot_agx_mean_difference'] = round(float(np.abs(read(empty_no_shadow[-1]) - expected).mean()), 3)
        for renderer in ['mobile', 'gl_compatibility']:
            files, _ = run(renderer, ['--at=4.9', '--no-ui'], renderer=renderer)
            diff = np.abs(base - read(files[-1]))
            result[renderer] = {'mean_channel_difference': round(float(diff.mean()), 3),
                                'share_pixels_gt8': round(float((diff.max(axis=2) > 8).mean()), 4),
                                'max_difference': int(diff.max())}
        late, _ = run('late', ['--t0=40', '--no-ui'])
        result['late_frame_std'] = round(float(read(late[-1]).std()), 2)
        result['frames_per_animation_run'] = len(key)
        result['native_size'] = [int(base.shape[1]), int(base.shape[0])]
        RESULT.write_text(json.dumps(result, indent=1, ensure_ascii=False))
        assert result['identical_runs'], 'Animation is not deterministic'
        assert result['catcher_pixels_changed_gt3'] > 100, 'Shadow catcher has no visible effect'
        assert result['catcher_darkened_pixels_gt3'] > 100 and result['catcher_lightened_pixels_gt3'] == 0, 'Catcher must darken the plate'
        assert result['catcher_without_character_max_difference'] <= 1, 'Catcher repeats baked environment shadows'
        assert result['panorama_pixels_changed_gt3'] > 100, 'Panorama has no visible effect'
        assert result['occlusion_max_share'] > 0.1, 'Depth does not occlude the character'
        assert not result['errors'], result['errors']
    RESULT.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
