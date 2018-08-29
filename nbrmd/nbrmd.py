"""Read and write notebooks as RStudio notebook files, with .Rmd extension.

Raw and markdown cells are converted to markdown, while code cells are
converted to code chunks. The transformation is reversible and all inputs
are preserved (not outputs, though).

Authors:

* Marc Wouts
"""

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------

import os
import io
from copy import deepcopy
from nbformat.v4.rwbase import NotebookReader, NotebookWriter
from nbformat.v4.nbbase import new_notebook
import nbformat

from .header import header_to_metadata_and_cell, metadata_and_cell_to_header, \
    encoding_and_executable
from .languages import get_default_language, find_main_language
from .cells import start_code_rmd, start_code_r, start_code_py
from .cells import text_to_cell
from .cells import markdown_to_cell_rmd, markdown_to_cell, code_to_cell
from .cell_to_text import CellExporter

# -----------------------------------------------------------------------------
# Code
# -----------------------------------------------------------------------------


NOTEBOOK_EXTENSIONS = ['.ipynb', '.Rmd', '.py', '.R']


def markdown_comment(ext):
    """Markdown escape for given notebook extension"""
    return '' if ext == '.Rmd' else "#'" if ext == '.R' else "#"


class TextNotebookReader(NotebookReader):
    """Text notebook reader"""

    def __init__(self, ext):
        self.ext = ext
        self.prefix = markdown_comment(ext)
        self.start_code = start_code_rmd if ext == '.Rmd' else \
            start_code_py if ext == '.py' else start_code_r
        if ext == '.Rmd':
            self.markdown_to_cell = markdown_to_cell_rmd

    header_to_metadata_and_cell = header_to_metadata_and_cell
    text_to_cell = text_to_cell
    code_to_cell = code_to_cell
    markdown_to_cell = markdown_to_cell

    def markdown_unescape(self, line):
        """Remove markdown escape, if any"""
        if self.prefix == '':
            return line
        line = line[len(self.prefix):]
        if line.startswith(' '):
            line = line[1:]
        return line

    def reads(self, s, **kwargs):
        """
        Read a notebook from a given string
        :param s:
        :param kwargs:
        :return:
        """
        return self.to_notebook(s, **kwargs)

    def to_notebook(self, text):
        """
        Read a notebook from its text representation
        :param text:
        :param kwargs:
        :return:
        """
        lines = text.splitlines()

        cells = []
        metadata, header_cell, pos = \
            self.header_to_metadata_and_cell(lines)

        if header_cell:
            cells.append(header_cell)

        if pos > 0:
            lines = lines[pos:]

        while lines:
            cell, pos = self.text_to_cell(lines)
            cells.append(cell)
            if pos <= 0:
                raise Exception('Blocked at lines ' + '\n'.join(lines[:6]))
            lines = lines[pos:]

        if self.ext == '.Rmd':
            find_main_language(metadata, cells)
        elif self.ext == '.R':
            if not (metadata.get('main_language') or
                    metadata.get('language_info', {})):
                metadata['main_language'] = 'R'

        nbk = new_notebook(cells=cells, metadata=metadata)
        return nbk


class TextNotebookWriter(NotebookWriter):
    """Write notebook to their text representations"""

    def __init__(self, ext='.Rmd'):
        self.ext = ext
        self.prefix = markdown_comment(ext)

    def markdown_escape(self, lines):
        """
        Escape markdown text
        :param lines:
        :return:
        """
        if self.prefix == '':
            return lines
        return [self.prefix if line == '' else self.prefix + ' ' + line
                for line in lines]

    encoding_and_executable = encoding_and_executable
    metadata_and_cell_to_header = metadata_and_cell_to_header

    def writes(self, nb, **kwargs):
        """Write the text representation of a notebook to a string"""
        nb = deepcopy(nb)
        if self.ext == '.py':
            default_language = (nb.metadata.get('main_language') or
                                nb.metadata.get('language_info', {})
                                .get('name', 'python'))
        elif self.ext == '.R':
            default_language = (nb.metadata.get('main_language') or
                                nb.metadata.get('language_info', {})
                                .get('name', 'R'))
            if nb.metadata.get('main_language') == 'R':
                del nb.metadata['main_language']
        else:
            default_language = get_default_language(nb)

        lines = self.encoding_and_executable(nb)
        lines.extend(self.metadata_and_cell_to_header(nb))

        cells = [CellExporter(cell, default_language, self.ext)
                 for cell in nb.cells]

        texts = [cell.cell_to_text() for cell in cells]

        for i, cell in enumerate(cells):
            text = texts[i]

            # remove end of cell marker when redundant
            # with next explicit marker
            if self.ext == '.py' and cell.is_code() and text[-1] == '# -':
                if i + 1 >= len(texts) or \
                        (texts[i + 1][0].startswith('# + {')):
                    text = text[:-1]

            lines.extend(text)
            lines.extend([''] * cell.skiplines)

            # two blank lines between markdown cells in Rmd
            if self.ext == '.Rmd' and not cell.is_code():
                if i + 1 < len(cells) and not cells[i + 1].is_code():
                    lines.append('')

        return '\n'.join(lines)


_NOTEBOOK_READERS = {ext: TextNotebookReader(ext)
                     for ext in NOTEBOOK_EXTENSIONS if ext != '.ipynb'}
_NOTEBOOK_WRITERS = {ext: TextNotebookWriter(ext)
                     for ext in NOTEBOOK_EXTENSIONS if ext != '.ipynb'}


def reads(text, as_version=4, ext='.Rmd', **kwargs):
    """Read a notebook from a string"""
    if ext == '.ipynb':
        return nbformat.reads(text, as_version, **kwargs)

    return _NOTEBOOK_READERS[ext].reads(text, **kwargs)


def read(file_or_stream, as_version=4, ext='.Rmd', **kwargs):
    """Read a notebook from a file"""
    if ext == '.ipynb':
        return nbformat.read(file_or_stream, as_version, **kwargs)

    return _NOTEBOOK_READERS[ext].read(file_or_stream, **kwargs)


def writes(notebook, version=nbformat.NO_CONVERT, ext='.Rmd', **kwargs):
    """Write a notebook to a string"""
    if ext == '.ipynb':
        return nbformat.writes(notebook, version, **kwargs)

    return _NOTEBOOK_WRITERS[ext].writes(notebook)


def write(notebook, file_or_stream, version=nbformat.NO_CONVERT, ext='.Rmd',
          **kwargs):
    """Write a notebook to a file"""
    if ext == '.ipynb':
        return nbformat.write(notebook, file_or_stream, version, **kwargs)

    return _NOTEBOOK_WRITERS[ext].write(notebook, file_or_stream)


def readf(nb_file):
    """Read a notebook from the file with given name"""
    _, ext = os.path.splitext(nb_file)
    if ext not in NOTEBOOK_EXTENSIONS:
        raise TypeError(
            'File {} is not a notebook. '
            'Expected extensions are {}'.format(nb_file,
                                                NOTEBOOK_EXTENSIONS))
    with io.open(nb_file, encoding='utf-8') as stream:
        return read(stream, as_version=4, ext=ext)


def writef(notebook, nb_file):
    """Write a notebook to the file with given name"""
    _, ext = os.path.splitext(nb_file)
    if ext not in NOTEBOOK_EXTENSIONS:
        raise TypeError(
            'File {} is not a notebook. '
            'Expected extensions are {}'.format(nb_file,
                                                NOTEBOOK_EXTENSIONS))
    with io.open(nb_file, 'w', encoding='utf-8') as stream:
        write(notebook, stream, version=nbformat.NO_CONVERT, ext=ext)
