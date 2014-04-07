# coding: utf-8
from fabric.api import puts


def _wrap_with(code):
    def inner(text, bold=False, bg=49):  # keep bg default if none
        c = code
        if bold:
            c = "1;%s" % (c)
        c = "%s;%s" % (c, bg)
        return "\033[%sm%s\033[0m" % (c, text)
    return inner


def puts_color(color):
    def inner(text, *args, **kwargs):
        return puts(color(text, *args, **kwargs))
    return inner


red = _wrap_with('31')
green = _wrap_with('32')
yellow = _wrap_with('33')
blue = _wrap_with('34')
magenta = _wrap_with('35')
cyan = _wrap_with('36')
white = _wrap_with('37')
bold = lambda str: '\033[1m%s\033[0m' % str

puts_red = puts_color(red)
puts_green = puts_color(green)
puts_yellow = puts_color(yellow)
puts_blue = puts_color(blue)
puts_magenta = puts_color(magenta)
puts_cyan = puts_color(cyan)
puts_white = puts_color(white)
