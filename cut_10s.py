import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_INPUT = r"C:\reint\124 [PNG_WEBP]\public\video\square_1x1"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}


def get_duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def cut(src: Path, dst: Path, start: float, duration: float, crf: int):
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", str(start), "-i", str(src), "-t", str(duration),
        "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def main():
    p = argparse.ArgumentParser(description="Potong video maksimal N detik")
    p.add_argument("--input", default=DEFAULT_INPUT, help="folder berisi video")
    p.add_argument("--output", default=None,
                   help="folder hasil (default: <input>_10s di sebelah folder input)")
    p.add_argument("--duration", type=float, default=10.0, help="durasi maksimal (detik)")
    p.add_argument("--start", type=float, default=0.0,
                   help="mulai potong dari detik ke-berapa (hanya untuk video yang dipotong)")
    p.add_argument("--crf", type=int, default=20, help="kualitas (lebih kecil = lebih bagus)")
    args = p.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            sys.exit(f"{tool} tidak ditemukan. Pastikan ffmpeg sudah terpasang dan ada di PATH.")

    in_dir = Path(args.input)
    if not in_dir.is_dir():
        sys.exit(f"Folder tidak ditemukan: {in_dir}")

    out_dir = Path(args.output) if args.output else in_dir.parent / f"{in_dir.name}_10s"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(f for f in in_dir.iterdir()
                   if f.is_file() and f.suffix.lower() in VIDEO_EXT)
    if not files:
        sys.exit("Tidak ada file video di folder tersebut.")

    print(f"{len(files)} video -> {out_dir} (maks {args.duration:g} detik)\n")
    cut_n = kept_n = 0
    failed = []

    for i, src in enumerate(files, 1):
        dst = out_dir / f"{src.stem}.mp4"
        if dst.exists():
            print(f"[{i}/{len(files)}] lewati (sudah ada): {src.name}")
            continue
        try:
            dur = get_duration(src)
            if dur <= args.duration + 0.05:
                shutil.copy2(src, dst)
                kept_n += 1
                print(f"[{i}/{len(files)}] {src.name}: {dur:.1f}s -> dibiarkan")
            else:
                cut(src, dst, args.start, args.duration, args.crf)
                cut_n += 1
                print(f"[{i}/{len(files)}] {src.name}: {dur:.1f}s -> dipotong")
        except (subprocess.CalledProcessError, ValueError):
            print(f"[{i}/{len(files)}] GAGAL: {src.name}")
            failed.append(src.name)

    print(f"\nSelesai. Dipotong: {cut_n}, dibiarkan: {kept_n}, gagal: {len(failed)}")
    if failed:
        print("Yang gagal:", ", ".join(failed))


if __name__ == "__main__":
    main()