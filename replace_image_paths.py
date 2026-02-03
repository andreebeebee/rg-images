#!/usr/bin/env python3
"""
Script per sostituire gli URL remoti delle immagini negli article.html
con i path locali relativi (image-2.webp, image-3.webp, ecc.)
"""

import os
import re
import argparse
from pathlib import Path


def find_article_folders(base_path: Path) -> list[Path]:
    """Trova tutte le cartelle che contengono article.html"""
    folders = []
    for subdir in ['articles', 'feedback-friday']:
        subdir_path = base_path / subdir
        if subdir_path.exists():
            for folder in subdir_path.iterdir():
                if folder.is_dir() and (folder / 'article.html').exists():
                    folders.append(folder)
    return sorted(folders)


def get_available_images(folder: Path) -> list[str]:
    """Restituisce la lista delle immagini disponibili nella cartella"""
    images = []
    for f in folder.iterdir():
        if f.name.startswith('image-') and f.name.endswith('.webp'):
            images.append(f.name)
    return sorted(images, key=lambda x: int(re.search(r'image-(\d+)', x).group(1)))


def extract_content_section(html: str) -> tuple[int, int, str]:
    """Estrae la sezione .content dall'HTML e restituisce start, end e contenuto"""
    match = re.search(r'(<div class="content">)(.*?)(</div>\s*</body>)', html, re.DOTALL)
    if match:
        start = match.start(2)
        end = match.end(2)
        return start, end, match.group(2)
    return -1, -1, ""


def replace_images_in_content(content: str, available_images: list[str], dry_run: bool, folder_name: str) -> tuple[str, list[dict]]:
    """Sostituisce gli URL delle immagini nel contenuto .content"""
    changes = []
    img_pattern = re.compile(r'<img\s+src="([^"]+)"')

    matches = list(img_pattern.finditer(content))

    if not matches:
        return content, changes

    # Costruisci il nuovo contenuto con le sostituzioni
    new_content = content
    offset = 0

    for i, match in enumerate(matches):
        image_index = i + 2  # Partiamo da image-2.webp
        expected_filename = f"image-{image_index}.webp"

        old_url = match.group(1)

        # Verifica se l'immagine esiste
        if expected_filename in available_images:
            new_url = expected_filename

            # Calcola le posizioni con l'offset
            start = match.start(1) + offset
            end = match.end(1) + offset

            # Registra il cambiamento
            changes.append({
                'index': i + 1,
                'old_url': old_url,
                'new_url': new_url,
                'exists': True
            })

            # Applica la sostituzione
            new_content = new_content[:start] + new_url + new_content[end:]
            offset += len(new_url) - len(old_url)
        else:
            changes.append({
                'index': i + 1,
                'old_url': old_url,
                'new_url': expected_filename,
                'exists': False
            })

    return new_content, changes


def process_article(folder: Path, dry_run: bool) -> dict:
    """Processa un singolo article.html"""
    article_path = folder / 'article.html'

    result = {
        'folder': folder.name,
        'path': str(folder),
        'changes': [],
        'errors': [],
        'images_in_html': 0,
        'images_available': 0
    }

    # Leggi il file HTML
    with open(article_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Ottieni le immagini disponibili
    available_images = get_available_images(folder)
    result['images_available'] = len(available_images)

    # Estrai la sezione .content
    start, end, content = extract_content_section(html)

    if start == -1:
        result['errors'].append("Sezione .content non trovata")
        return result

    # Sostituisci le immagini
    new_content, changes = replace_images_in_content(content, available_images, dry_run, folder.name)
    result['changes'] = changes
    result['images_in_html'] = len(changes)

    # Verifica mismatch
    images_with_files = sum(1 for c in changes if c['exists'])
    if images_with_files != len(changes):
        missing = [c for c in changes if not c['exists']]
        result['errors'].append(f"{len(missing)} immagini mancanti: {[c['new_url'] for c in missing]}")

    # Scrivi il file se non è dry-run e ci sono cambiamenti
    if not dry_run and changes:
        new_html = html[:start] + new_content + html[end:]
        with open(article_path, 'w', encoding='utf-8') as f:
            f.write(new_html)

    return result


def main():
    parser = argparse.ArgumentParser(description='Sostituisce URL immagini con path locali negli article.html')
    parser.add_argument('--dry-run', action='store_true', help='Mostra le modifiche senza applicarle')
    args = parser.parse_args()

    # Determina il path base
    base_path = Path(__file__).parent

    print(f"{'[DRY-RUN] ' if args.dry_run else ''}Elaborazione articoli in: {base_path}")
    print("=" * 80)

    # Trova tutte le cartelle con article.html
    folders = find_article_folders(base_path)
    print(f"Trovate {len(folders)} cartelle con article.html\n")

    total_changes = 0
    total_errors = 0

    for folder in folders:
        result = process_article(folder, args.dry_run)

        if result['changes'] or result['errors']:
            print(f"\n📁 {result['folder']}")
            print(f"   Immagini nell'HTML: {result['images_in_html']}, File disponibili: {result['images_available']}")

            if result['changes']:
                for change in result['changes'][:3]:  # Mostra solo le prime 3
                    status = "✓" if change['exists'] else "✗"
                    old_short = change['old_url'][-40:] if len(change['old_url']) > 40 else change['old_url']
                    print(f"   {status} [{change['index']}] ...{old_short} → {change['new_url']}")

                if len(result['changes']) > 3:
                    print(f"   ... e altre {len(result['changes']) - 3} sostituzioni")

                total_changes += len(result['changes'])

            if result['errors']:
                for error in result['errors']:
                    print(f"   ⚠️  {error}")
                total_errors += len(result['errors'])

    print("\n" + "=" * 80)
    print(f"{'[DRY-RUN] ' if args.dry_run else ''}Riepilogo:")
    print(f"  - Cartelle elaborate: {len(folders)}")
    print(f"  - Sostituzioni {'da effettuare' if args.dry_run else 'effettuate'}: {total_changes}")
    print(f"  - Avvisi: {total_errors}")

    if args.dry_run and total_changes > 0:
        print(f"\nPer applicare le modifiche, esegui: python {Path(__file__).name}")


if __name__ == '__main__':
    main()
