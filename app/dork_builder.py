def build_dork(title=None, author=None, publisher=None, year=None, filetypes=None, site=None, frase=None):
    parts = []

    if title:
        parts.append(f'intitle:"{title}"')

    if frase:
        parts.append(f'intext:"{frase}"')

    if author:
        parts.append(f'"{author}"')

    if publisher:
        parts.append(f'"{publisher}"')

    if year:
        parts.append(str(year))

    if site:
        parts.append(f'site:"{site}"')

    if filetypes:
        types = " OR ".join([f"filetype:{t}" for t in filetypes])
        parts.append(f"({types})")
    


    return " ".join(parts) if parts else "books"