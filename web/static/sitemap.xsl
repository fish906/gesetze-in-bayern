<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="2.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:sitemap="http://www.sitemaps.org/schemas/sitemap/0.9">

<xsl:output method="html" indent="yes" encoding="UTF-8"/>

<xsl:template match="/">
<html lang="de">
<head>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>Sitemap — BayRecht</title>
    <link href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;700&amp;family=DM+Sans:wght@400;500;600&amp;display=swap" rel="stylesheet"/>
    <style>
        :root {
            --color-bg: #FAFAF7;
            --color-surface: #FFFFFF;
            --color-text: #1A1A18;
            --color-text-secondary: #5C5C57;
            --color-accent: #8B2500;
            --color-border: #E5E4DF;
            --color-border-light: #F0EFEB;
            --color-highlight: #FFF8F0;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: 'DM Sans', system-ui, sans-serif;
            background: var(--color-bg);
            color: var(--color-text);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
        }

        .container {
            max-width: 860px;
            margin: 0 auto;
            padding: 2.5rem 2rem 4rem;
        }

        h1 {
            font-family: 'Crimson Pro', Georgia, serif;
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 0.4rem;
        }

        h1 span { color: var(--color-accent); }

        .subtitle {
            font-size: 0.95rem;
            color: var(--color-text-secondary);
            margin-bottom: 2rem;
        }

        .count {
            font-size: 0.85rem;
            color: var(--color-text-secondary);
            margin-bottom: 1rem;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: 6px;
            overflow: hidden;
        }

        thead th {
            text-align: left;
            font-size: 0.78rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--color-text-secondary);
            padding: 0.8rem 1rem;
            background: var(--color-bg);
            border-bottom: 1px solid var(--color-border);
        }

        tbody tr {
            border-bottom: 1px solid var(--color-border-light);
        }

        tbody tr:last-child {
            border-bottom: none;
        }

        tbody tr:hover {
            background: var(--color-highlight);
        }

        td {
            padding: 0.6rem 1rem;
            font-size: 0.88rem;
        }

        td a {
            color: var(--color-accent);
            text-decoration: none;
            word-break: break-all;
        }

        td a:hover {
            text-decoration: underline;
        }

        .priority {
            font-size: 0.8rem;
            color: var(--color-text-secondary);
            text-align: center;
        }

        @media (max-width: 640px) {
            .container { padding: 1.5rem 1rem 3rem; }
            h1 { font-size: 1.5rem; }
            td, th { padding: 0.5rem 0.6rem; font-size: 0.82rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bay<span>Recht</span> Sitemap</h1>
        <p class="subtitle">Alle indexierten Seiten dieser Website</p>
        <p class="count">
            <xsl:value-of select="count(sitemap:urlset/sitemap:url)"/> Seiten
        </p>
        <table>
            <thead>
                <tr>
                    <th>URL</th>
                    <th style="width: 80px; text-align: center;">Priorität</th>
                </tr>
            </thead>
            <tbody>
                <xsl:for-each select="sitemap:urlset/sitemap:url">
                    <tr>
                        <td>
                            <a href="{sitemap:loc}"><xsl:value-of select="sitemap:loc"/></a>
                        </td>
                        <td class="priority">
                            <xsl:value-of select="sitemap:priority"/>
                        </td>
                    </tr>
                </xsl:for-each>
            </tbody>
        </table>
    </div>
</body>
</html>
</xsl:template>
</xsl:stylesheet>
