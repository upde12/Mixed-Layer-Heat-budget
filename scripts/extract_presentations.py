#!/usr/bin/env python3
import sys
import os
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict


NS = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
}


def _strip_text(s: str) -> str:
    if not s:
        return ""
    # normalize whitespace, remove excessive spaces
    return "\n".join(line.strip() for line in s.replace("\r", "\n").split("\n") if line.strip())


def extract_pptx(path: str):
    slides = {}
    notes = {}
    if not zipfile.is_zipfile(path):
        return slides, notes
    with zipfile.ZipFile(path) as z:
        # Collect slide files in order
        slide_files = sorted((name for name in z.namelist() if name.startswith('ppt/slides/slide') and name.endswith('.xml')),
                             key=lambda n: int(os.path.splitext(os.path.basename(n))[0].replace('slide', '')))
        for sf in slide_files:
            try:
                data = z.read(sf)
                root = ET.fromstring(data)
                texts = []
                # Extract all a:t text runs
                for t in root.findall('.//a:t', NS):
                    if t.text:
                        texts.append(t.text)
                sidx = int(os.path.splitext(os.path.basename(sf))[0].replace('slide', ''))
                slides[sidx] = _strip_text("\n".join(texts))
            except Exception as e:
                sidx = int(os.path.splitext(os.path.basename(sf))[0].replace('slide', ''))
                slides[sidx] = f"[슬라이드 파싱 오류: {e}]"

        # Notes (optional)
        notes_files = sorted((name for name in z.namelist() if name.startswith('ppt/notesSlides/notesSlide') and name.endswith('.xml')),
                             key=lambda n: int(os.path.splitext(os.path.basename(n))[0].replace('notesSlide', '')))
        for nf in notes_files:
            try:
                data = z.read(nf)
                root = ET.fromstring(data)
                texts = []
                for t in root.findall('.//a:t', NS):
                    if t.text:
                        texts.append(t.text)
                nidx = int(os.path.splitext(os.path.basename(nf))[0].replace('notesSlide', ''))
                notes[nidx] = _strip_text("\n".join(texts))
            except Exception as e:
                nidx = int(os.path.splitext(os.path.basename(nf))[0].replace('notesSlide', ''))
                notes[nidx] = f"[노트 파싱 오류: {e}]"
    return slides, notes


def extract_docx(path: str):
    paragraphs = []
    if not zipfile.is_zipfile(path):
        return paragraphs
    with zipfile.ZipFile(path) as z:
        try:
            data = z.read('word/document.xml')
            root = ET.fromstring(data)
            # Each w:p is a paragraph; collect w:t within
            for p in root.findall('.//w:p', NS):
                texts = []
                for t in p.findall('.//w:t', NS):
                    if t.text:
                        texts.append(t.text)
                para = _strip_text("".join(texts))
                if para:
                    paragraphs.append(para)
        except KeyError:
            pass
    return paragraphs


STOPWORDS = set(
    [
        # Korean stopwords (minimal, extendable)
        '및', '등', '및', '또는', '그리고', '그러나', '이', '그', '저', '의', '에', '를', '이란', '에서', '으로', '으로써', '와', '과', '하다', '했다', '있는', '없는', '등의', '및',
        # English stopwords (minimal)
        'the','and','of','to','in','for','on','with','as','by','is','are','be','from','at','that','this','it','we','a','an','or','not','into','can','using','use','used','via'
    ]
)


def keyword_counts(text: str, topn: int = 10):
    # naive tokenization by non-alphanumeric split preserving Korean
    import re
    tokens = re.findall(r"[A-Za-z]+|[0-9]+|[\uAC00-\uD7A3]+", text)
    tokens = [t.lower() for t in tokens if t.strip()]
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
    return Counter(tokens).most_common(topn)


def summarize_pptx(slides: dict, notes: dict):
    # Build a list of (idx, title, lines)
    items = []
    for idx in sorted(slides.keys()):
        content = slides[idx]
        lines = content.split('\n') if content else []
        title = next((ln for ln in lines if ln.strip()), '').strip()
        items.append((idx, title, lines))
    all_text = "\n".join(slides[i] for i in sorted(slides))
    kwords = keyword_counts(all_text)
    return items, kwords


def save_text_dump(out_dir: str, base: str, slides: dict, notes: dict, paragraphs=None):
    os.makedirs(out_dir, exist_ok=True)
    if slides:
        for idx in sorted(slides):
            fp = os.path.join(out_dir, f"{base}_slide_{idx:02d}.txt")
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(slides[idx])
    if notes:
        for idx in sorted(notes):
            fp = os.path.join(out_dir, f"{base}_notes_{idx:02d}.txt")
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(notes[idx])
    if paragraphs is not None:
        fp = os.path.join(out_dir, f"{base}.txt")
        with open(fp, 'w', encoding='utf-8') as f:
            f.write("\n\n".join(paragraphs))


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description='Extract and summarize presentation contents')
    ap.add_argument('--root', default='presentation', help='Directory containing pptx/docx files')
    ap.add_argument('--out', default='presentation/_extracted', help='Output directory for text dumps')
    ap.add_argument('--summary', default='presentation/_extracted/summary.md', help='Path to write summary markdown')
    args = ap.parse_args(argv)

    files = []
    for dirpath, _, filenames in os.walk(args.root):
        for name in filenames:
            if name.lower().endswith(('.pptx', '.docx')):
                files.append(os.path.join(dirpath, name))

    os.makedirs(args.out, exist_ok=True)

    report_lines = []
    report_lines.append(f"# Presentation Summary\n")

    for fpath in sorted(files):
        base = os.path.splitext(os.path.basename(fpath))[0]
        rel = os.path.relpath(fpath)
        report_lines.append(f"## {base}")
        report_lines.append(f"- File: `{rel}`")
        if fpath.lower().endswith('.pptx'):
            slides, notes = extract_pptx(fpath)
            save_text_dump(args.out, base, slides, notes)
            items, kwords = summarize_pptx(slides, notes)
            report_lines.append(f"- Slides: {len(items)}")
            if kwords:
                kw = ", ".join(f"{w}({c})" for w, c in kwords[:10])
                report_lines.append(f"- Keywords: {kw}")
            # List slide titles (first non-empty line)
            report_lines.append(f"- Slide titles (first line):")
            for idx, title, _ in items:
                t = title if title else "(제목 텍스트 없음)"
                report_lines.append(f"  - {idx:02d}: {t}")
            if notes:
                report_lines.append(f"- Notes available: {len(notes)} slides")
        else:  # docx
            paras = extract_docx(fpath)
            save_text_dump(args.out, base, {}, {}, paragraphs=paras)
            report_lines.append(f"- Paragraphs: {len(paras)}")
            # Show first 5 non-empty paragraphs as preview
            for i, p in enumerate(paras[:5], 1):
                preview = p
                if len(preview) > 120:
                    preview = preview[:117] + '...'
                report_lines.append(f"  - P{i}: {preview}")

        report_lines.append("")

    # Write summary
    with open(args.summary, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))

    print(f"Summary written to {args.summary}")
    print(f"Text dumps saved under {args.out}")


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

