# coding: utf-8


def _wrap_with(code):
    def inner(text, bold=False, bg=49):  # keep bg default if none
        c = code
        if bold:
            c = "1;%s" % (c)
        c = "%s;%s" % (c, bg)
        return "\033[%sm%s\033[0m" % (c, text)
    return inner

red = _wrap_with('31')
green = _wrap_with('32')
yellow = _wrap_with('33')
blue = _wrap_with('34')
magenta = _wrap_with('35')
cyan = _wrap_with('36')
white = _wrap_with('37')
bold = lambda str: '\033[1m%s\033[0m' % str
