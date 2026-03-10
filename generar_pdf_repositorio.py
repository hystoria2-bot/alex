#!/usr/bin/env python3
"""Genera un PDF simple con información del repositorio sin dependencias externas."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "Resumen_repositorio.pdf"


@dataclass
class RepoFile:
    name: str
    size_kb: float
    kind: str
    extra: str


def estimate_pdf_pages(path: Path) -> str:
    """Estimación simple del número de páginas contando objetos /Type /Page."""
    try:
        data = path.read_bytes()
    except OSError:
        return "No se pudo leer"
    matches = re.findall(rb"/Type\s*/Page\b", data)
    if matches:
        return str(len(matches))
    return "No detectado"


def detect_kind_and_extra(path: Path) -> tuple[str, str]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "PDF", f"Páginas estimadas: {estimate_pdf_pages(path)}"
    if ext == ".docx":
        return "DOCX", "Documento editable"
    return ext.lstrip(".").upper() or "Archivo", ""


def collect_files(root: Path) -> list[RepoFile]:
    files: list[RepoFile] = []
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        if path.name in {OUTPUT.name, Path(__file__).name}:
            continue
        kind, extra = detect_kind_and_extra(path)
        files.append(
            RepoFile(
                name=path.name,
                size_kb=path.stat().st_size / 1024,
                kind=kind,
                extra=extra,
            )
        )
    return files


def escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(lines: list[str], output: Path) -> None:
    objects: list[bytes] = []

    # 1) Catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # 2) Pages
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    # 3) Page
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
    )
    # 4) Font
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    content_parts = [b"BT", b"/F1 11 Tf", b"50 800 Td", b"14 TL"]
    first = True
    for line in lines:
        safe = escape_pdf_text(line)
        if first:
            content_parts.append(f"({safe}) Tj".encode("latin-1", errors="replace"))
            first = False
        else:
            content_parts.append(b"T*")
            content_parts.append(f"({safe}) Tj".encode("latin-1", errors="replace"))
    content_parts.append(b"ET")
    stream = b"\n".join(content_parts)
    objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode())
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode()
    )

    output.write_bytes(pdf)


def main() -> None:
    files = collect_files(ROOT)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    total_size = sum(f.size_kb for f in files)
    pdf_count = sum(1 for f in files if f.kind == "PDF")
    docx_count = sum(1 for f in files if f.kind == "DOCX")

    lines = [
        "Resumen funcional del repositorio",
        f"Generado: {now}",
        "",
        "Visión general:",
        f"- Archivos analizados: {len(files)}",
        f"- PDFs: {pdf_count}",
        f"- DOCX: {docx_count}",
        f"- Tamaño total aprox: {total_size:.1f} KB",
        "",
        "Detalle de archivos:",
    ]

    for idx, item in enumerate(files, start=1):
        lines.append(f"{idx}. {item.name}")
        lines.append(f"   Tipo: {item.kind} | Tamaño: {item.size_kb:.1f} KB")
        if item.extra:
            lines.append(f"   {item.extra}")

    lines.append("")
    lines.append("Nota: Para regenerar este reporte ejecuta:")
    lines.append("python generar_pdf_repositorio.py")

    build_pdf(lines, OUTPUT)
    print(f"PDF generado en: {OUTPUT}")


if __name__ == "__main__":
    main()
