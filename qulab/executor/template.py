import ast
import base64
import hashlib
import lzma
import pickle
import re
import string
import textwrap
from typing import Any

_notset = object()


def VAR(name: str, /, *, default: Any = _notset) -> Any:
    return name


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


class TemplateTypeError(TypeError):
    pass


class TemplateKeyError(KeyError):
    pass


class TemplateVarExtractor(ast.NodeVisitor):

    def __init__(self, fname, mapping):
        self.var_func_def = (0, 0)
        self.variables = set()
        self.str_variables = set()
        self.replacements = {}
        self.fname = fname
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
            if not isinstance(arg, ast.Constant) or not isinstance(
                    arg.value, str):
                raise SyntaxError(
                    f"Argument of VAR function must be a string. {self.fname}:{node.lineno}"
                )
            if len(node.args) != 1:
                raise SyntaxError(
                    f"VAR function only accept one argument. {self.fname}:{node.lineno}"
                )
            default = _notset
            for k in node.keywords:
                if k.arg == 'default':
                    pass
                    # if isinstance(k.value, ast.Constant):
                    #     # default = k.value.value
                    #     default = k.value
                    # else:
                    #     default = k.value
                    #     # raise SyntaxError(
                    #     #     f"Argument of 'default' must be a constant. {self.fname}:{node.lineno}"
                    #     # )
                else:
                    raise SyntaxError(
                        f"VAR function only accept keyword argument 'default'. {self.fname}:{node.lineno}"
                    )

            if default is _notset:
                # new_node = ast.Subscript(value=ast.Name(id="__VAR",
                #                                         ctx=ast.Load()),
                #                          slice=ast.Constant(value=arg.value),
                #                          ctx=ast.Load())
                if arg.value not in self.mapping:
                    raise TemplateKeyError(
                        f"The variable '{arg.value}' is not provided in mapping. {self.fname}:{node.lineno}"
                    )
                self.replacements[(node.lineno, node.end_lineno,
                                   node.col_offset,
                                   node.end_col_offset)] = ('VAR', arg.value,
                                                            None, None)
            else:
                # new_node = ast.Call(
                #     func=ast.Attribute(value=ast.Name(id='__VAR',
                #                                       ctx=ast.Load()),
                #                        attr='get',
                #                        ctx=ast.Load()),
                #     args=[ast.Constant(value=arg.value)],
                #     keywords=[
                #         ast.keyword(arg='default',
                #                     value=value)
                #     ],
                #     ctx=ast.Load())
                self.replacements[(node.lineno, node.end_lineno,
                                   node.col_offset,
                                   node.end_col_offset)] = ('VAR', arg.value,
                                                            None, None)
            # ast.fix_missing_locations(new_node)
            # new_source = ast.unparse(new_node)
            # print(new_source)

            self.variables.add(arg.value)

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
                    raise TemplateKeyError(
                        f"The variable '{var_name}' is not provided in mapping. {self.fname}:{current_lineno}"
                    )
                if not isinstance(self.mapping[var_name], str):
                    raise TemplateTypeError(
                        f"Mapping value for '{var_name}' must be a string. {self.fname}:{current_lineno}"
                    )
                self.str_variables.add(var_name)
                start, stop = 0, len(line)
                if current_lineno == lineno:
                    start = col_offset
                if current_lineno == end_lineno:
                    stop = end_col_offset
                self.replacements[(current_lineno, current_lineno, start,
                                   stop)] = ('STR', var_name, None, None)


def inject_mapping(source: str, mapping: dict[str, Any],
                   fname: str) -> list[tuple[str, int]]:
    hash_str, mapping_code = encode_mapping(mapping)

    tree = ast.parse(source)

    lines = source.splitlines()
    lines_offset = [0 for _ in range(len(lines))]

    extractor = TemplateVarExtractor(fname, mapping)
    extractor.visit(tree)

    # remove VAR function definition
    if extractor.var_func_def != (0, 0):
        for i in range(extractor.var_func_def[0] - 1,
                       extractor.var_func_def[1]):
            lines[i] = ''

    for (lineno, end_lineno, col_offset,
         end_col_offset), (kind, name, old_source,
                           new_source) in extractor.replacements.items():
        head = lines[lineno - 1][:col_offset + lines_offset[lineno - 1]]
        tail = lines[end_lineno - 1][end_col_offset +
                                     lines_offset[end_lineno - 1]:]
        length_of_last_line = len(lines[end_lineno - 1])
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
                lines_offset[lineno -
                             1] += len(lines[lineno - 1]) - length_of_last_line
            else:
                lines[lineno - 1:end_lineno] = formated_lines
                lines_offset[end_lineno - 1] += len(
                    lines[end_lineno - 1]) - length_of_last_line
        else:
            pattern = re.compile(
                r'VAR\s*\(\s*'                # VAR(
                r'(["\'])(\w+)\1'             # 捕获引号和变量名
                r'(?:\s*,\s*default\s*=\s*'   # 匹配 default 参数
                r'([^),]*)'                   # 捕获 default 值（排除逗号和括号）
                r')?'                         # 可选参数组
                r'\s*\)',                     # 闭合括号
                re.DOTALL
            ) # yapf: disable

            def replacement(match):
                quote = match.group(1)
                var_name = match.group(2)
                default_value = match.group(3)

                base = f'__VAR_{hash_str}'
                if default_value is not None:
                    # 清除 default 值前后的空格
                    clean_value = default_value.strip()
                    return f'{base}.get({quote}{var_name}{quote}, {clean_value})'
                else:
                    return f'{base}[{quote}{var_name}{quote}]'

            new_content = re.sub(pattern, replacement, content)

            if lineno == end_lineno:
                lines[lineno - 1] = head + new_content + tail
                lines_offset[lineno -
                             1] += len(lines[lineno - 1]) - length_of_last_line
            else:
                lines[lineno - 1] = head + new_content[:-1]
                for i in range(lineno, end_lineno - 1):
                    lines[i] = ''
                lines[end_lineno - 1] = new_content[-1] + tail
                lines_offset[end_lineno - 1] += len(
                    lines[end_lineno - 1]) - length_of_last_line

    injected_code = '\n'.join([
        f"__QULAB_TEMPLATE__ = \"{fname}\"",
        f"from qulab.executor.template import decode_mapping as __decode_{hash_str}",
        f"__VAR_{hash_str} = __decode_{hash_str}(\"{hash_str}\", \"\"\"",
        mapping_code, "    \"\"\")", *lines
    ])

    return injected_code, hash_str
