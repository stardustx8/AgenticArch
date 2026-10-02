def render_title(text):
    safe = text.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
    return f'<h1>{safe}</h1>'


def render_item(text):
    safe = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return f'<li>{safe}</li>'


def render_list(items):
    return '<ul>' + ''.join(render_item(item) for item in items) + '</ul>'


def render_link(url, label):
    href = url.replace('"', '&quot;').replace('&', '&amp;')
    text = label.replace('<', '&lt;').replace('>', '&gt;').replace('&', '&amp;')
    return f'<a href="{href}">{text}</a>'
