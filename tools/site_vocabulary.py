"""Project the maintained editorial vocabulary; never treat it as BGSM semantics."""
import re
from markdown_it import MarkdownIt
from tools.validate_publication import require


def vocabulary(path):
    source = path.read_text()
    version = re.search(r'\*\*Draft ([0-9]+\.[0-9]+)', source)
    require(version is not None, 'Vocabulary needs an explicit editorial draft version')
    tokens = MarkdownIt('commonmark').enable('table').parse(source)
    group, cells, terms = '', [], []
    in_table = False
    for i, token in enumerate(tokens):
        if token.type == 'heading_open' and token.tag == 'h2':
            group = tokens[i+1].content
        if token.type == 'tbody_open': in_table = True
        if token.type == 'tbody_close': in_table = False
        if in_table and token.type == 'tr_open': cells = []
        if in_table and token.type == 'inline':
            cells.append(''.join(t.content for t in token.children or [] if t.type in {'text','code_inline'}))
        if in_table and token.type == 'tr_close':
            require(len(cells) == 2, 'Vocabulary rows need a term and meaning')
            slug = re.sub(r'[^a-z0-9]+', '-', cells[0].lower()).strip('-')
            terms.append({'id':slug,'title':cells[0],'meaning':cells[1],'group':group})
    require(terms and len({t['id'] for t in terms}) == len(terms), 'Vocabulary IDs must be unique')
    return {'version':version[1],'status':'editorial-draft','terms':terms}
