from markupsafe import Markup
from flask import url_for

default_th_renderer = lambda title: f'<th>{ title }</th>'

default_td_renderer = lambda obj, value: f'<td>{ value }</td>'

class Table:

    def __init__(self, attributes, th_renderer=None, td_renderer=None):
        self.attributes = attributes
        if th_renderer is None:
            th_renderer = default_th_renderer
        self.th_renderer = th_renderer
        if td_renderer is None:
            td_renderer = default_td_renderer
        self.td_renderer = td_renderer

    def get_title(self, class_attr):
        info = getattr(class_attr, 'info', {})
        return info.get('title')

    def render_thead_row(self, class_):
        titles = [self.get_title(getattr(class_, first_name(attr))) for attr in self.attributes]
        ths = ''.join(self.th_renderer(title) for title in titles)
        return Markup(f'<tr>{ ths }</tr>')

    def get_td_renderer(self, obj, attr):
        info = getattr(attr, 'info', {})
        renderer = info.get('renderer', self.td_renderer)
        return renderer

    def render_tbody_row(self, obj):
        values = [rgetattr(obj, attr) for attr in self.attributes]
        renderers = [self.get_td_renderer(obj, attr) for attr in self.attributes]
        tds = ''.join([renderer(obj, value) for value, renderer in zip(values, renderers)])
        return Markup(f'<tr>{ tds }</tr>')


class Link:

    def __init__(self, endpoint_for_instance, attribute, identity):
        self.endpoint_for_instance = endpoint_for_instance
        self.attribute = attribute
        self.identity = identity

    def render(self, instance):
        href = url_for(self.endpoint_for_instance, **self.identity(instance))
        return Markup(f'<a href="{ href }">{ getattr(instance, self.attribute) }</a>')


def rgetattr(obj, attribute):
    names = attribute.split('.')
    value = getattr(obj, names[0])
    for name in names[1:]:
        value = getattr(value, name)
    return value

def first_name(attribute):
    if '.' not in attribute:
        return attribute
    else:
        names = attribute.split('.')
        return names[0]
