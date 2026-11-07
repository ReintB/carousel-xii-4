#!/usr/bin/env python3
r"""
Opsi:
    --out         folder hasil (default: <folder_input>\carousel_out)
    --per-slide   jumlah video per slide (default 4 -> grid 2x2)
    --max-slides  maksimal slide per postingan (default 20)
    --size        ukuran sisi video hasil dalam px (default 1080)
    --fps         frame rate hasil (default 30)
    --fill        freeze = video pendek berhenti di frame terakhir (default)
                  loop   = video pendek diulang sampai slide selesai
    --audio       none  = tanpa suara (default)
                  first = pakai suara video pertama di tiap slide
    --max-duration potong tiap video maksimal sekian detik (default 10)
    --fit         crop = potong bagian tengah jadi 1:1 (default)
                  pad  = video utuh, sisa area diisi bar hitam
    --shuffle     acak urutan video (default: urut nama file)
    --dry-run     hanya tampilkan pembagian slide, tidak render
"""
import argparse
import random
import subprocess
import sys
from pathlib import Path


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def probe_video(path: Path):
    """Kembalikan (ada_video, info_teks)."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,pix_fmt",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    lines = [l for l in r.stdout.strip().splitlines() if l]
    has_video = any(l.startswith("video") or ",video" in l or "video" in l.split(",")[0:1] for l in lines)
    # csv urutan field ffprobe: codec_name,codec_type,... -> cek kata 'video'
    has_video = any("video" in l.split(",") for l in lines)
    info = " | ".join(lines) if lines else (r.stderr.strip() or "TIDAK TERBACA")
    return has_video, info


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def build_cmd(group, durs, out_file, cell, size, fps, fill, audio, per_slide, max_dur, fit):
    durs = [min(d, max_dur) for d in durs]
    dur = max(durs)
    cols = 2 if per_slide <= 4 else 3
    cmd = ["ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error"]

    for f in group:
        if fill == "loop":
            cmd += ["-stream_loop", "-1"]
        else:
            cmd += ["-t", f"{max_dur:.3f}"]
        cmd += ["-i", str(f)]

    filters = []
    for i in range(len(group)):
        if fit == "pad":
            geo = (f"scale={cell}:{cell}:force_original_aspect_ratio=decrease,"
                   f"pad={cell}:{cell}:(ow-iw)/2:(oh-ih)/2:color=black")
        else:
            geo = (f"scale={cell}:{cell}:force_original_aspect_ratio=increase,"
                   f"crop={cell}:{cell}")
        chain = f"[{i}:v]{geo},setsar=1,fps={fps},format=yuv420p"
        if fill == "freeze":
            pad = max(dur - durs[i], 0) + 0.1
            chain += f",tpad=stop_mode=clone:stop_duration={pad:.3f}"
        filters.append(chain + f"[v{i}]")

    labels = [f"[v{i}]" for i in range(len(group))]
    for j in range(len(group), per_slide):
        filters.append(f"color=c=black:s={cell}x{cell}:r={fps}:d={dur:.3f},format=yuv420p[v{j}]")
        labels.append(f"[v{j}]")

    layout = "|".join(
        f"{(k % cols) * cell}_{(k // cols) * cell}" for k in range(per_slide)
    )
    filters.append("".join(labels) +
                   f"xstack=inputs={per_slide}:layout={layout}:fill=black,"
                   f"trim=duration={dur:.3f},setpts=PTS-STARTPTS[out]")

    cmd += ["-filter_complex", ";".join(filters), "-map", "[out]"]
    if audio == "first":
        cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += ["-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_file)]
    return cmd


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?", default=None,
                    help="folder berisi video .mp4 (default: folder tempat skrip ini berada)")
    ap.add_argument("--out")
    ap.add_argument("--per-slide", type=int, default=4, choices=[4, 9])
    ap.add_argument("--max-slides", type=int, default=20)
    ap.add_argument("--size", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--fill", choices=["freeze", "loop"], default="freeze")
    ap.add_argument("--audio", choices=["none", "first"], default="none")
    ap.add_argument("--max-duration", type=float, default=10.0,
                    help="potong tiap video maksimal sekian detik (default 10)")
    ap.add_argument("--fit", choices=["crop", "pad"], default="crop",
                    help="crop = potong tengah jadi 1:1 (default); pad = utuh, sisa diberi bar hitam")
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = Path(a.input) if a.input else Path(__file__).resolve().parent
    videos = sorted(p for p in src.iterdir()
                    if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm", ".m4v"})
    if not videos:
        sys.exit("Tidak ada file video di folder tersebut.")
    if a.shuffle:
        random.shuffle(videos)

    cols = 2 if a.per_slide == 4 else 3
    cell = a.size // cols
    size = cell * cols
    out_root = Path(a.out) if a.out else src / "carousel_out"

    slides = list(chunks(videos, a.per_slide))
    posts = list(chunks(slides, a.max_slides))
    print(f"{len(videos)} video -> {len(slides)} slide -> {len(posts)} postingan "
          f"(maks {a.max_slides} slide/postingan)")

    for pi, post in enumerate(posts, 1):
        for si, group in enumerate(post, 1):
            print(f"  post{pi}/slide{si:02d}: " + ", ".join(v.stem for v in group))
    if a.dry_run:
        return

    import shutil
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"'{tool}' tidak ditemukan di PATH. Pasang FFmpeg dulu "
                     f"(winget install Gyan.FFmpeg) lalu buka ulang VS Code.")
    ver = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[:1]
    print("FFmpeg:", ver[0] if ver else "?", "->", shutil.which("ffmpeg"))

    print("\nMemeriksa isi tiap file video ...")
    report, bad = [], []
    for v in videos:
        ok, info = probe_video(v)
        report.append(f"{'OK ' if ok else 'BAD'} {v.name}: {info}")
        if not ok:
            bad.append(v.name)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "probe_report.txt").write_text("\n".join(report), encoding="utf-8")
    print(f"{len(videos) - len(bad)} file OK, {len(bad)} file TIDAK punya aliran video.")
    if bad:
        print("Contoh file bermasalah:", ", ".join(bad[:5]))
        print(f"Detail lengkap: {out_root / 'probe_report.txt'}")
        sys.exit("Render dibatalkan. Perbaiki/convert dulu file di atas "
                 "(lihat probe_report.txt), atau pindahkan keluar dari folder.")
    print()

    log = []
    for pi, post in enumerate(posts, 1):
        folder = out_root / f"post_{pi}"
        folder.mkdir(parents=True, exist_ok=True)
        for si, group in enumerate(post, 1):
            durs = [probe_duration(v) or 1.0 for v in group]
            out_file = folder / f"slide_{si:02d}.mp4"
            print(f"[post {pi}/{len(posts)}] render {out_file.name} "
                  f"({len(group)} video, {min(max(durs), a.max_duration):.1f}s)")
            cmd = build_cmd(group, durs, out_file, cell, size, a.fps, a.fill, a.audio, a.per_slide,
                            a.max_duration, a.fit)
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0:
                err = r.stderr.strip()
                print("  GAGAL:", err[:300], "...", err[-300:] if len(err) > 600 else "")
                if out_file.exists():
                    out_file.unlink()
                continue
            log.append(f"post_{pi}/{out_file.name}: " + " | ".join(v.name for v in group))

    (out_root / "daftar_slide.txt").write_text("\n".join(log), encoding="utf-8")
    print(f"\nSelesai. Hasil: {out_root}")


if __name__ == "__main__":
    main()