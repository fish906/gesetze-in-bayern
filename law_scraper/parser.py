from bs4 import BeautifulSoup
import re

SUPERSCRIPT_MAP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹'
}

def to_superscript(number_str):
    return ''.join(SUPERSCRIPT_MAP.get(ch, ch) for ch in number_str)

def extract_text_with_sup(elem):
    parts = []
    for child in elem.children:
        if getattr(child, 'name', None) == 'sup' and 'satznr' in child.get('class', []):
            parts.append(f"<sup>{child.get_text(strip=True)}</sup>")
        elif isinstance(child, str):
            parts.append(child)
        else:
            parts.append(child.get_text())
            
    return ''.join(parts).strip()

def parse_norm(html):
    soup = BeautifulSoup(html, 'html.parser')

    para_heading = soup.find('div', class_='paraheading')
    number_text = para_heading.find('div', class_='paranr').get_text(strip=True)
    number_raw_match = re.search(r'(\d+[a-z]?)', number_text, re.IGNORECASE)
    number_raw = number_raw_match.group(1) if number_raw_match else number_text

    title_div = para_heading.find('div', class_='paratitel')
    title = title_div.get_text(strip=True) if title_div else ''

    content_parts = []
    container = soup.find('div', class_='cont')
    children = list(container.children)

    i = 0
    while i < len(children):
        child = children[i]

        if getattr(child, 'name', None) == 'div' and 'paratext' in child.get('class', []):
            paragraph = extract_text_with_sup(child)
            content_parts.append(f"<p>{paragraph}</p>")

            if i + 1 < len(children):
                next_elem = children[i + 1]
                if getattr(next_elem, 'name', None) == 'dl':
                    list_items = []
                    for dt in next_elem.find_all('dt'):
                        dd = dt.find_next_sibling('dd')
                        if dd:
                            dd_div = dd.find('div', class_='paratext')
                            dd_text = extract_text_with_sup(dd_div if dd_div else dd)
                            list_items.append(f"<li>{dd_text}</li>")
                    if list_items:
                        content_parts.append("<ol>" + "\n".join(list_items) + "</ol>")
                    i += 1 

        # Liste ohne vorherigen Absatz (z. B. am Ende)
        elif getattr(child, 'name', None) == 'dl':
            list_items = []
            for dt in child.find_all('dt'):
                dd = dt.find_next_sibling('dd')
                if dd:
                    dd_div = dd.find('div', class_='paratext')
                    dd_text = extract_text_with_sup(dd_div if dd_div else dd)
                    list_items.append(f"<li>{dd_text}</li>")
            if list_items:
                content_parts.append("<ol>" + "\n".join(list_items) + "</ol>")

        i += 1

    content_html = "\n".join(content_parts)

    return {
        'number': number_text,
        'number_raw': number_raw,
        'title': title,
        'content': content_html,
        'references': []
    }
