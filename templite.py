import re


class CodeBuilder(object):
    """用于添加代码、控制缩进等功能
        @indent 生成代码缩进
    """

    def __init__(self, indent=0):
        self.code = []
        self.indent_level = indent

    def add_line(self, line):
        '''加入代码及缩进'''
        self.code.extend([" " * self.indent_level, line, "\n"])

    INDENT_STEP = 4  # 缩进格式为4个空格

    def indent(self):
        '''增加一级缩进'''
        self.indent_level += self.INDENT_STEP

    def dedent(self):
        '''减少一级缩进'''
        self.indent_level -= self.INDENT_STEP

    def add_section(self):
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    def __str__(self):
        """设置转化为字符串的格式"""
        return "".join(str(c) for c in self.code)

    def get_globals(self):
        """运行代码并返回名字空间词典"""
        # 检查缩进，保证所有块（block）都已经处理完
        assert self.indent_level == 0
        # 生产代码
        python_source = str(self)
        # 设置命名空间，并返还命名空间
        globals_namespace = {}
        exec(python_source, globals_namespace)
        return globals_namespace


class Templite(object):
    """docstring for Templite"""

    def __init__(self, text, *contexts):
        self.context = {}
        for context in contexts:
            self.context.update(context)

        # 所有的变量名
        self.all_vars = set()
        # 属于循环的变量名
        self.loop_vars = set()

        code = CodeBuilder()
        # 对部分代码硬编码加入code中
        code.add_line("def render_function(context, do_dots):")
        code.indent()
        vars_code = code.add_section()  # 将提取变量的部分代码空出，解析完模板后在加入
        code.add_line("result = []")
        code.add_line("append_result = result.append")
        code.add_line("expend_result = result.expend")
        code.add_line("to_str = str")

        buffered = []  # 缓存队列

        def flush_output(self):
            """将缓存中的代码加入code，并清空缓存"""
            if len(buffered) == 1:
                code.add_line("append_result(%s)" % buffered[0])
            elif len(buffered) > 1:
                code.add_line("extend_result(%s)" % ', '.join(buffered))
            del buffered[:]

        ops_stack = []  # 用栈来检查嵌套语法

        # 对模板内容解析
        # (?s)是改变.匹配模式的flags
        tokens = re.split(r'(?s)({{.*?}}|{%.*?%}|{#.*?#})', text)
        for token in tokens:
            if token.startswith('{#'):
                continue
            elif token.startswith('{{'):
                # _expr_code函数将模板解析成python表达式
                expr = self._expr_code(token[2:-2].strip())
                buffered.append('to_str(%s)' % expr)
            elif token.startswith('{%'):
                flush_output()  # 解析{%  %}标签中的内容
                words = token[2:-2].strip().split()
                if words[0] == 'if':
                    if len(words) != 2:
                        # _syntax_error函数会报出异常
                        self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line("if {}:".format(self._expr_code(words[1])))
                    code.indent()
                elif words[0] == 'for':
                    if len(words) != 4 or words[2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append("for")
                    # _variable函数校验变量合法性，然后补充vars_code
                    self._variable(words[1], self.loop_vars)
                    code.add_line(
                        "for c_%s in %s:" % (
                            words[1],
                            self._expr_code(words[3])
                        )
                    )
                    code.indent()
                elif words[0].startswith('end'):
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    if start_what != end_what:
                        self._syntax_error("Mismatched end tag", end_what)
                    code.dedent()