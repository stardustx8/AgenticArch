def _escape_text(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _escape_attr(value):
    return value.replace('&', '&amp;').replace('"', '&quot;')


def render_title(text):
    return f'<h1>{_escape_text(text)}</h1>'


def render_item(text):
    return f'<li>{_escape_text(text)}</li>'


def render_list(items):
    return '<ul>' + ''.join(render_item(item) for item in items) + '</ul>'


def render_link(url, label):
    return f'<a href="{_escape_attr(url)}">{_escape_text(label)}</a>'
