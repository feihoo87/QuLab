import ast
import base64
import hashlib
import lzma
import pickle
import re
import string
import textwrap
from typing import Any


def encode_mapping(mapping):
    mapping_bytes = lzma.compress(pickle.dumps(mapping))
    hash_str = hashlib.md5(mapping_bytes).hexdigest()[:8]
    mappping_code = '\n'.join(
        textwrap.wrap(base64.b64encode(mapping_bytes).decode(),
                      90,
                      initial_indent='    ',
                      subsequent_indent='    '))
    return hash_str, mappping_code


def decode_mapping(hash_str, mappping_code):
    mapping_bytes = base64.b64decode(mappping_code)
    if hash_str != hashlib.md5(mapping_bytes).hexdigest()[:8]:
        raise ValueError("Hash does not match")
    mapping = pickle.loads(lzma.decompress(mapping_bytes))
    return mapping


class TemplateVarExtractor(ast.NodeVisitor):

    def __init__(self, mapping):
        self.var_func_def = (0, 0)
        self.variables = set()
        self.str_variables = set()
        self.replacements = {}
        self.mapping = mapping

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self._process_string(node.value, node.lineno, node.col_offset,
                                 node.end_lineno, node.end_col_offset)

    def visit_JoinedStr(self, node):
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(
                    value.value, str):
                self._process_string(value.value, value.lineno,
                                     value.col_offset, value.end_lineno,
                                     value.end_col_offset)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if node.name == 'VAR':
            self.var_func_def = (node.lineno, node.end_lineno)
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == 'VAR':
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if arg.value not in self.mapping:
                    raise KeyError(
                        f"The variable '{arg.value}' in line {node.lineno} is not provided in mapping."
                    )
                self.variables.add(arg.value)
                # new_node = ast.Subscript(value=ast.Name(id="__VAR",
                #                                         ctx=ast.Load()),
                #                          slice=ast.Constant(value=arg.value),
                #                          ctx=ast.Load())
                # ast.fix_missing_locations(new_node)
                # new_source = ast.unparse(new_node)
                self.replacements[(node.lineno, node.end_lineno,
                                   node.col_offset,
                                   node.end_col_offset)] = ('VAR', arg.value,
                                                            None, None)
            else:
                raise ValueError(
                    f"Argument of VAR function must be a string in line {node.lineno}"
                )
        self.generic_visit(node)

    def _process_string(self, s: str, lineno: int, col_offset: int,
                        end_lineno: int, end_col_offset: int):
        """解析字符串内容，提取模板变量"""
        lines = s.split('\n')
        for offset, line in enumerate(lines):
            current_lineno = lineno + offset
            template = string.Template(line)
            for var_name in template.get_identifiers():
                if var_name not in self.mapping:
                    raise KeyError(
                        f"The variable '{var_name}' in line {current_lineno} is not provided in mapping."
                    )
                if not isinstance(self.mapping[var_name], str):
                    raise TypeError(
                        f"Mapping value for '{var_name}' must be a string in line {current_lineno}"
                    )
                self.str_variables.add(var_name)
                start, stop = 0, len(line)
                if current_lineno == lineno:
                    start = col_offset
                if current_lineno == end_lineno:
                    stop = end_col_offset
                self.replacements[(current_lineno, current_lineno, start,
                                   stop)] = ('STR', var_name, None, None)


def inject_mapping(source: str, mapping: dict[str,
                                              Any]) -> list[tuple[str, int]]:
    title, _ = encode_mapping(mapping)

    tree = ast.parse(source)
    lines = source.splitlines()
    extractor = TemplateVarExtractor(mapping)
    extractor.visit(tree)

    # remove VAR function definition
    if extractor.var_func_def != (0, 0):
        for i in range(extractor.var_func_def[0] - 1,
                       extractor.var_func_def[1]):
            lines[i] = ''

    hash_str, mapping_code = encode_mapping(
        {k: mapping[k]
         for k in extractor.variables})

    for (lineno, end_lineno, col_offset,
         end_col_offset), (kind, name, old_source,
                           new_source) in extractor.replacements.items():
        head = lines[lineno - 1][:col_offset]
        tail = lines[end_lineno - 1][end_col_offset:]
        content = lines[lineno - 1:end_lineno]
        content[0] = content[0].removeprefix(head)
        content[-1] = content[-1].removesuffix(tail)
        content = '\n'.join(content)

        if kind == 'STR':
            template = string.Template(content)
            formated_lines = template.substitute(mapping).splitlines()
            formated_lines[0] = head + formated_lines[0]
            formated_lines[-1] = formated_lines[-1] + tail
            if len(formated_lines) == 1:
                lines[lineno - 1] = formated_lines[0]
            else:
                lines[lineno - 1:end_lineno] = formated_lines
        else:
            pattern = re.compile(r'VAR\s*\(\s*(["\'])(\w+)\1\s*\)')
            replacement = f'__VAR_{hash_str}' + r'[\1\2\1]'
            new_content = re.sub(pattern, replacement, content)

            if lineno == end_lineno:
                lines[lineno - 1] = head + new_content + tail
            else:
                lines[lineno - 1] = head + new_content[:-1]
                for i in range(lineno, end_lineno - 1):
                    lines[i] = ''
                lines[end_lineno - 1] = ']' + tail

    code = '\n'.join(lines)
    inject_code = '\n'.join([
        "from qulab.executor.template import decode_mapping",
        f"__VAR_{hash_str} = decode_mapping(\"{hash_str}\", \"\"\"",
        mapping_code, "    \"\"\")", ""
    ])

    return inject_code + code, title
