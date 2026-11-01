"""Pinned cmap and literal stylesheet coverage, not browser/visual acceptance."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
FONT_NAMES=('schibsted-grotesk-latin-ext-wght-normal.woff2',
            'schibsted-grotesk-latin-wght-normal.woff2')
STYLESHEETS={'storymotion/compose.py':1,'storymotion/template_families.py':1,
             'renderers/remotion/entry.jsx':2}


def cmap_fixture():
    return json.loads((ROOT/'tests/fixtures/font-cmaps.json').read_text())['fonts']


def ranges(value):
    points=set()
    for token in value.split(','):
        match=re.fullmatch(r'U\+([0-9A-Fa-f]{4,6})(?:-([0-9A-Fa-f]{4,6}))?',token.strip())
        if not match:raise AssertionError('Unexpected literal font range')
        start=int(match[1],16);end=int(match[2] or match[1],16)
        if not 0<=start<=end<=0x10FFFF:raise AssertionError('Invalid font range')
        points.update(range(start,end+1))
    return points


def stylesheet_groups(relative):
    source=(ROOT/relative).read_text()
    # Inspect only fixed font-face literals; never evaluate Python/JS/template data.
    source=re.sub(r"\$\{staticFile\('([A-Za-z0-9/_.-]+)'\)\}",r'\1',source)
    source=source.replace('{{','{').replace('}}','}')
    faces=[]
    for face in re.findall(r'@font-face\{([^}]+)\}',source):
        names=[name for name in FONT_NAMES if name in face]
        if len(names)!=1:raise AssertionError('Unexpected font-face source')
        scope=re.search(r'unicode-range:([^;}]+)',face)
        faces.append({'name':names[0],'points':ranges(scope[1]) if scope else None})
    if len(faces)!=2*STYLESHEETS[relative]:raise AssertionError('Stylesheet count changed')
    return [faces[index:index+2] for index in range(0,len(faces),2)]


def selected_font(point,faces,cmaps):
    for face in reversed(faces):
        if (face['points'] is None or point in face['points']) and point in cmaps[face['name']]['codepoints']:
            return face['name']
    return None


class FontRangeTests(unittest.TestCase):
    def test_cmap_snapshot_binds_exact_existing_font_bytes(self):
        fonts=cmap_fixture();self.assertEqual(set(fonts),set(FONT_NAMES))
        for name,value in fonts.items():
            with self.subTest(font=name):
                self.assertEqual(hashlib.sha256((ROOT/'vendor/fonts'/name).read_bytes()).hexdigest(),value['sha256'])
                self.assertEqual(value['codepoints'],sorted(set(value['codepoints'])))
                self.assertTrue(all(type(point) is int and 0<=point<=0x10FFFF for point in value['codepoints']))
        self.assertIn(0x131,fonts[FONT_NAMES[1]]['codepoints'])
        self.assertNotIn(0x131,fonts[FONT_NAMES[0]]['codepoints'])

    def test_every_stylesheet_selects_latin_font_for_dotless_i(self):
        for relative in STYLESHEETS:
            for index,faces in enumerate(stylesheet_groups(relative)):
                with self.subTest(source=relative,branch=index):
                    self.assertEqual(selected_font(0x131,faces,cmap_fixture()),FONT_NAMES[1])

    def test_existing_family_range_is_shared_by_all_latin_declarations(self):
        expected=stylesheet_groups('storymotion/template_families.py')[0][1]['points']
        for relative in STYLESHEETS:
            for index,faces in enumerate(stylesheet_groups(relative)):
                with self.subTest(source=relative,branch=index):
                    self.assertEqual([face['name'] for face in faces],list(FONT_NAMES))
                    self.assertIsNone(faces[0]['points'])
                    self.assertEqual(faces[1]['points'],expected)

    def test_all_existing_font_glyphs_remain_available_in_each_pair(self):
        fonts=cmap_fixture();points=set().union(*(value['codepoints'] for value in fonts.values()))
        for relative in STYLESHEETS:
            for index,faces in enumerate(stylesheet_groups(relative)):
                with self.subTest(source=relative,branch=index):
                    self.assertEqual([point for point in points if selected_font(point,faces,fonts) is None],[])

    def test_mixed_turkish_case_and_punctuation_have_a_pinned_glyph(self):
        for relative in STYLESHEETS:
            for faces in stylesheet_groups(relative):
                for character in 'IİıiÇçĞğÖöŞşÜü — “”.€↑↓':
                    with self.subTest(source=relative,character=character):
                        self.assertIsNotNone(selected_font(ord(character),faces,cmap_fixture()))

    def test_dotless_regression_is_detected_without_rejecting_other_letters(self):
        faces=stylesheet_groups('storymotion/template_families.py')[0]
        faces=[dict(face) for face in faces];faces[1]['points']=faces[1]['points']-{0x131}
        self.assertIsNone(selected_font(0x131,faces,cmap_fixture()))
        self.assertEqual(selected_font(ord('I'),faces,cmap_fixture()),FONT_NAMES[1])
        self.assertEqual(selected_font(ord('İ'),faces,cmap_fixture()),FONT_NAMES[0])


if __name__=='__main__':unittest.main()
