import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_INPUT = r"C:\reint\124 [PNG_WEBP]\public\video"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}


def build_filter(mode: str, size: int, y_offset: float) -> list[str]:
    if mode == "crop":
        vf = (
            f"crop=min(iw\\,ih):min(iw\\,ih):(iw-ow)/2:(ih-oh)*{y_offset},"
            f"scale={size}:{size},setsar=1"
        )
        return ["-vf", vf]

    fc = (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={size}:{size}:force_original_aspect_ratio=increase,"
        f"crop={size}:{size},boxblur=25:5[bg2];"
        f"[fg]scale={size}:{size}:force_original_aspect_ratio=decrease[fg2];"
        f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2,setsar=1[v]"
    )
    return ["-filter_complex", fc, "-map", "[v]"]


def convert(src: Path, dst: Path, mode: str, size: int, y_offset: float, crf: int):
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        *build_filter(mode, size, y_offset),
        "-map", "0:a?",                  # ikutkan audio kalau ada
        "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def main():
    p = argparse.ArgumentParser(description="Ubah video ke rasio 1:1")
    p.add_argument("--input", default=DEFAULT_INPUT, help="folder berisi video")
    p.add_argument("--output", default=None, help="folder hasil (default: <input>/square_1x1)")
    p.add_argument("--mode", choices=["crop", "blur"], default="crop")
    p.add_argument("--size", type=int, default=1080, help="sisi kotak dalam piksel")
    p.add_argument("--y-offset", type=float, default=0.5,
                   help="khusus mode crop: 0=atas, 0.5=tengah, 1=bawah")
    p.add_argument("--crf", type=int, default=20, help="kualitas (lebih kecil = lebih bagus)")
    args = p.parse_args()

    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg tidak ditemukan. Install dulu, lalu pastikan ada di PATH.")

    in_dir = Path(args.input)
    if not in_dir.is_dir():
        sys.exit(f"Folder tidak ditemukan: {in_dir}")

    out_dir = Path(args.output) if args.output else in_dir / "square_1x1"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(f for f in in_dir.iterdir() if f.suffix.lower() in VIDEO_EXT)
    if not files:
        sys.exit("Tidak ada file video di folder tersebut.")

    print(f"{len(files)} video -> {out_dir} (mode: {args.mode}, {args.size}x{args.size})")
    failed = []
    for i, src in enumerate(files, 1):
        dst = out_dir / f"{src.stem}.mp4"
        if dst.exists():
            print(f"[{i}/{len(files)}] lewati (sudah ada): {src.name}")
            continue
        print(f"[{i}/{len(files)}] {src.name}")
        try:
            convert(src, dst, args.mode, args.size, args.y_offset, args.crf)
        except subprocess.CalledProcessError:
            print(f"   GAGAL: {src.name}")
            failed.append(src.name)

    print("\nSelesai.")
    if failed:
        print("Yang gagal:", ", ".join(failed))


if __name__ == "__main__":
    main()