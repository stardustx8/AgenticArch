class TemplateError(Exception):
    """Base class for template errors."""


class TemplateSyntaxError(TemplateError):
    """The template source is malformed."""


class UndefinedError(TemplateError):
    """A variable or attribute used by the template does not exist."""
