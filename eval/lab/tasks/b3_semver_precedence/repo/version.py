from functools import total_ordering


@total_ordering
class Version:
    def __init__(self, major, minor, patch, prerelease=(), build=()):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = tuple(prerelease)
        self.build = tuple(build)

    @classmethod
    def parse(cls, text):
        core, _, build = text.strip().partition('+')
        core, _, pre = core.partition('-')
        parts = core.split('.')
        if len(parts) != 3 or not all(p.isascii() and p.isdigit() for p in parts):
            raise ValueError('invalid version: %r' % (text,))
        major, minor, patch = (int(p) for p in parts)
        prerelease = tuple(pre.split('.')) if pre else ()
        build_ids = tuple(build.split('.')) if build else ()
        return cls(major, minor, patch, prerelease, build_ids)

    def _key(self):
        return (self.major, self.minor, self.patch, self.prerelease)

    def __eq__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() == other._key()

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() < other._key()

    def __hash__(self):
        return hash(self._key())

    def __str__(self):
        text = '%d.%d.%d' % (self.major, self.minor, self.patch)
        if self.prerelease:
            text += '-' + '.'.join(self.prerelease)
        if self.build:
            text += '+' + '.'.join(self.build)
        return text

    def __repr__(self):
        return 'Version(%r)' % (str(self),)
