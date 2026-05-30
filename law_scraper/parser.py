from bs4 import BeautifulSoup
import re
import logging
from datetime import date

logger = logging.getLogger("law_scraper.parser")

SUPERSCRIPT_MAP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹'
}

def to_superscript(number_str):
    return ''.join(SUPERSCRIPT_MAP.get(ch, ch) for ch in number_str)

def extract_text_with_sup(elem):
    parts = []
    for child in elem.children:
        tag = getattr(child, 'name', None)
        if tag is None:
            parts.append(str(child))
        elif tag == 'sup':
            parts.append(f"<sup>{child.get_text(strip=True)}</sup>")
        elif tag in ('em', 'i'):
            parts.append(f"<em>{extract_text_with_sup(child)}</em>")
        elif tag in ('strong', 'b'):
            parts.append(f"<strong>{extract_text_with_sup(child)}</strong>")
        elif tag == 'br':
            parts.append('<br>')
        elif tag == 'a':
            parts.append(child.get_text())
        else:
            parts.append(child.get_text())
    return ''.join(parts).strip()

class ParseError(Exception):
    """Raised when a page does not contain the expected norm structure."""
    pass


def process_dl(dl_elem):
    """Recursively convert a <dl> structure to an HTML <ol>."""
    items = []
    for dt in dl_elem.find_all('dt', recursive=False):
        dd = dt.find_next_sibling('dd')
        if not dd:
            continue
        dd_div = dd.find('div', class_='paratext')
        text = extract_text_with_sup(dd_div if dd_div else dd)
        nested = dd.find('dl')
        if nested:
            text += process_dl(nested)
        items.append(f"<li>{text}</li>")
    if not items:
        return ""
    return "<ol>" + "\n".join(items) + "</ol>"

def parse_norm(html):
    soup = BeautifulSoup(html, 'html.parser')

    para_heading = soup.find('div', class_='paraheading')
    if not para_heading:
        raise ParseError("No 'paraheading' div found — page may not contain a norm")

    paranr_div = para_heading.find('div', class_='paranr')
    if not paranr_div:
        raise ParseError("No 'paranr' div found within paraheading")

    number_text = paranr_div.get_text(strip=True)
    number_raw_match = re.search(r'(\d+[a-z]?)', number_text, re.IGNORECASE)
    number_raw = number_raw_match.group(1) if number_raw_match else number_text

    title_div = para_heading.find('div', class_='paratitel')
    title = title_div.get_text(strip=True) if title_div else ''

    content_parts = []
    container = soup.find('div', class_='cont')
    if not container:
        logger.warning(f"No 'cont' div found for norm '{number_text}' — content will be empty")
        return {
            'number': number_text,
            'number_raw': number_raw,
            'title': title,
            'content': '',
            'references': []
        }

    children = list(container.children)

    i = 0
    while i < len(children):
        child = children[i]
        child_tag = getattr(child, 'name', None)

        if child_tag == 'div' and 'paratext' in child.get('class', []):
            paragraph = extract_text_with_sup(child)
            content_parts.append(f"<p>{paragraph}</p>")

            if i + 1 < len(children):
                next_elem = children[i + 1]
                if getattr(next_elem, 'name', None) == 'dl':
                    ol = process_dl(next_elem)
                    if ol:
                        content_parts.append(ol)
                    i += 1

        elif child_tag == 'dl':
            ol = process_dl(child)
            if ol:
                content_parts.append(ol)

        elif child_tag == 'table':
            rows = []
            for tr in child.find_all('tr'):
                cells = [
                    f"<td>{extract_text_with_sup(td)}</td>"
                    for td in tr.find_all(['td', 'th'])
                ]
                if cells:
                    rows.append(f"<tr>{''.join(cells)}</tr>")
            if rows:
                content_parts.append(f"<table>{''.join(rows)}</table>")

        i += 1

    content_html = "\n".join(content_parts)

    return {
        'number': number_text,
        'number_raw': number_raw,
        'title': title,
        'content': content_html,
        'references': []
    }

def parse_overview(html):
    soup = BeautifulSoup(html, 'html.parser')

    metadata = soup.find('div', id='doc-metadata')
    search_root = metadata if metadata else soup

    for div in search_root.find_all('div'):
        text = div.get_text(" ", strip=True)
        if 'Text gilt ab:' not in text:
            continue
        m = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', text)
        if m:
            day, month, year = map(int, m.groups())
            try:
                return date(year, month, day)
            except ValueError:
                return None

    return None