from bs4 import BeautifulSoup

# Mapping 0–9 zu Unicode-Hochzahlen
SUPERSCRIPT_MAP = {
    '0': '⁰',
    '1': '¹',
    '2': '²',
    '3': '³',
    '4': '⁴',
    '5': '⁵',
    '6': '⁶',
    '7': '⁷',
    '8': '⁸',
    '9': '⁹'
}

def to_superscript(number_str):
    """Wandelt eine Ziffernfolge in Unicode-Hochzahlen um."""
    return ''.join(SUPERSCRIPT_MAP.get(ch, ch) for ch in number_str)

def extract_text_with_unicode_sup(div):
    """Extrahiert den Paragraftext mit Satznummern als Unicode-Hochzahlen."""
    texts = []
    for elem in div.children:
        if getattr(elem, 'name', None) == 'sup' and 'satznr' in elem.get('class', []):
            num = elem.get_text(strip=True)
            texts.append(to_superscript(num))
        elif isinstance(elem, str):
            texts.append(elem)
        else:
            texts.append(elem.get_text())
    return ''.join(texts).strip()

def parse_norm(html):
    soup = BeautifulSoup(html, 'html.parser')

    # Nummer
    number = soup.find('div', class_='paraheading').find('div', class_='paranr').get_text(strip=True)

    # Titel
    title = soup.find('div', class_='paraheading').find('div', class_='paratitel').get_text(strip=True)

    # Inhalt mit Unicode Hochzahlen
    content_divs = soup.find_all('div', class_='paratext')
    content = ''
    for div in content_divs:
        content += extract_text_with_unicode_sup(div) + '\n'

    # Platzhalter für Referenzen (später)
    references = []

    return {
        'number': number,
        'number_raw': number,
        'title': title,
        'content': content.strip(),
        'references': references
    }
