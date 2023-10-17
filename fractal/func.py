import ast
from typing import Type, Tuple, Optional, List, Dict, Sequence
import warnings

import math
import cmath


GLSL_FRACTAL_FUNC_NAME = "fractal_func"
GLSL_NAME_FORMAT = "_fractal_uniform_%s"
PY_FRACTAL_FUNC_NAME = "_generated_fractal_function"

class CompilationException:
    def __init__(self, reason: str, is_warning: bool, node: ast.AST = None, err: SyntaxError = None):
        self.reason = reason
        self.is_warning = is_warning
        if node is None and err is None:
            self.lineno = self.col_offset = self.end_lineno = self.end_col_offset = None
            return
        if node is not None:
            self.lineno: int = node.lineno
            self.col_offset: int = node.col_offset
            self.end_lineno: Optional[int] = node.end_lineno
            self.end_col_offset: Optional[int] = node.end_col_offset
        else:
            self.lineno = err.lineno
            self.col_offset = err.offset
            self.end_lineno = err.end_lineno
            self.end_col_offset = err.end_offset

class CompilationError(CompilationException, Exception):
    def __init__(self, reason: str, node: ast.AST = None, err: SyntaxError = None):
        super().__init__(reason, False, node, err)

class CompilationWarning(CompilationException, Warning):
    def __init__(self, reason: str, node: ast.AST = None, err: SyntaxError = None):
        super().__init__(reason, True, node, err)

_NumberAnyType = int | float | complex
_VarTypes = _NumberAnyType | bool

class Uniform:
    def __init__(self, fractal: "FractalFunction", name: str, typ: Type[_VarTypes]):
        self.__fractal = fractal
        self.name = name
        self.typ = typ
        self.__value = ...  # TODO

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, val):
        old_val = self.__value
        self.__value = val
        if old_val != val:
            self.__fractal.updateUniforms()

class FractalFunction:
    def __init__(self, source: str):
        self._source = source
        self._ast: Optional[ast.Module] = None
        self.uniforms: Optional[Tuple[Uniform]] = None
        self._uniform_dict = None
        self._glsl_func_body: Optional[Sequence[str]] = None
        self.func = None
        # Indicates weather a resolve attempt was made (only one attempt should be made for each Fractal object!)
        self._attempted_resolve = False
        self._resolved = False

    @staticmethod
    def _glslAsFloat(expr: str, tp: Type):
        if tp is float:
            return expr
        if tp is int:
            return f"FLOAT({expr})"
        if tp is complex:
            return f"({expr}).x"
        return None
    @staticmethod
    def _glslAsComplex(expr: str, tp: Type):
        if tp is complex:
            return expr
        if tp is float or tp is int:
            expr = FractalFunction._glslAsFloat(expr, tp)
            return f"VEC2({expr},0.)"
        return None

    @staticmethod
    def _getVarType(name: str, variables: List[Tuple[str, Type[_VarTypes]] | Uniform]) -> Optional[Type[_VarTypes]]:
        for var in variables:
            if type(var) is tuple:
                if var[0] == name:
                    # noinspection PyTypeChecker
                    return var[1]
            else:
                if var.name == name:
                    return var.typ
        return None

    # noinspection PyUnresolvedReferences
    @staticmethod
    def _astToGLSL(node: ast.AST, variables: List[Tuple[str, Type[_VarTypes]] | Uniform]) -> Tuple[str, Optional[Type]]:
        match type(node):
            case ast.Constant:
                val_type = type(node.value)
                if val_type is int or val_type is float:
                    return repr(node.value), val_type
                elif val_type is bool:
                    return ("true" if node.value else "false"), bool
                else:
                    raise CompilationError(f"Unsupported constant type '{val_type}'", node)
            case ast.Name:
                if type(node.ctx) is not ast.Load:
                    raise CompilationError("We should not reach here! STH WENT WRONG", node)
                typ = FractalFunction._getVarType(node.id, variables)
                if typ is None:
                    raise CompilationError(f"Variable '{node.id}' is not defined", node)
                return node.id, typ
            case ast.Assign:
                ...
            case ast.AnnAssign:
                ...
            case ast.AugAssign:
                ...
            case ast.UnaryOp:
                operand, operand_type = FractalFunction._astToGLSL(node.operand, variables)
                match type(node.op):
                    case ast.UAdd:
                        if issubclass(operand_type, _NumberAnyType):
                            return f"({operand})", operand_type
                        raise CompilationError(f"Unary add not supported for '{operand_type.__name__}'", node)
                    case ast.USub:
                        if issubclass(operand_type, _NumberAnyType):
                            return f"-({operand})", operand_type
                        raise CompilationError(f"Negation not supported for '{operand_type.__name__}'", node)
                    case ast.Not:
                        if operand_type is bool:
                            return f"!({operand})", bool
                        raise CompilationError(f"Not operation not supported for '{operand_type.__name__}'", node)
                raise CompilationError(f"Unsupported unary operation '{type(node.op).__name__}'", node)
            case ast.BinOp:
                left, left_type = FractalFunction._astToGLSL(node.left, variables)
                right, right_type = FractalFunction._astToGLSL(node.right, variables)
                if not (issubclass(left_type, _NumberAnyType) and issubclass(right_type, _NumberAnyType)):
                    raise CompilationError(f"Binary operations only support numeric types, got '{left_type.__name__}' and '{right_type.__name__}'", node)
                match type(node.op):
                    case ast.Add | ast.Sub | ast.Mult | ast.Div as op_type:
                        output_type = int
                        if left_type is complex or right_type is complex:
                            left = FractalFunction._glslAsComplex(left, left_type)
                            right = FractalFunction._glslAsComplex(right, right_type)
                            output_type = complex
                        elif left_type is float or right_type is float:
                            left = FractalFunction._glslAsFloat(left, left_type)
                            right = FractalFunction._glslAsFloat(right, right_type)
                            output_type = float
                        match op_type:
                            case ast.Add:
                                return f"({left}+{right})", output_type
                            case ast.Sub:
                                return f"({left}-{right})", output_type
                            case ast.Mult:
                                return (f"cx_mul({left},{right})" if output_type is complex else f"({left}*{right})"), output_type
                            case ast.Div:
                                return (f"cx_div({left},{right})" if output_type is complex else f"({left}/{right})"), output_type
                    case ast.Pow:
                        if left_type is complex or right_type is complex:
                            if right == "2":
                                return f"cx_sqr({left})", complex
                            if right == "3":
                                return f"cx_cube({left})", complex
                            left = FractalFunction._glslAsComplex(left, left_type)
                            right = FractalFunction._glslAsComplex(right, right_type)
                            return f"cx_pow({left},{right})", complex
                        left = FractalFunction._glslAsFloat(left, left_type)
                        right = FractalFunction._glslAsFloat(right, right_type)
                        return f"pow({left},{right})", float
                    case ast.Mod:
                        if left_type is int and right_type is int:
                            return f"({left}%{right})", int
                        elif left_type is float and (right_type is float or right_type is int):
                            right = FractalFunction._glslAsFloat(right, right_type)
                            return f"mod({left},{right})", float
                        raise CompilationError(f"Modulo is not supported between '{left_type.__name__}' and '{right_type.__name__}'", node)
                raise CompilationError(f"Unsupported binary operation '{type(node.op).__name__}'", node)
            case ast.Call:
                pass  # TODO
            case ast.BoolOp:
                infix = "||" if type(node.op) is ast.Or else "&&"
                exps = []
                for exp_ast in node.values:
                    expr, expr_type = FractalFunction._astToGLSL(exp_ast, variables)
                    if expr_type is not bool:
                        raise CompilationError(f"Boolean operation not supported for {expr_type.__name__}.", node)
                    exps.append(f"({expr})")
                return infix.join(exps), bool
            case ast.IfExp:
                test, test_type = FractalFunction._astToGLSL(node.test, variables)
                if test_type is not bool:
                    raise CompilationError(f"Test expression must evaluate to a boolean, got {test_type.__name__}.", node)
                body, body_type = FractalFunction._astToGLSL(node.body, variables)
                els, els_type = FractalFunction._astToGLSL(node.orelse, variables)
                if body_type is not els_type:
                    raise CompilationError(f"Branches of if expression must evaluate to the same type, got {body_type.__name__} and {els_type.__name__}.", node)
                return f"({test}?{body}:{els})", body_type
            case ast.Return:
                return f"return {FractalFunction._astToGLSL(node.value, variables)[0]};", None
            case ast.Expr:
                warnings.warn(CompilationWarning("Result unused.", node))
                return FractalFunction._astToGLSL(node.value, variables)
            case ast.Pass:
                return "", None
        raise CompilationError(f"Unsupported operation {type(node).__name__}.", node)

    @staticmethod
    def _stripUniformFromStmt(stmt: ast.stmt) -> Optional[Uniform]:
        """
        Tries to resolve a uniform variable from the statement, if it is not a uniform definition, return None.
        """
        ...  # TODO: uniform stuff

    @staticmethod
    def _generateNameSpaceForExec():
        return {
            "pi": math.pi,
            "e": math.e,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "exp": math.exp,
            "log": math.log,
            "cx_sin": cmath.sin,
            "cx_cos": cmath.cos,
            "cx_tan": cmath.tan,
            "cx_exp": cmath.exp,
            "cx_log": cmath.log,
        }

    def resolve(self, compile_glsl=True):
        """
        Generate the GLSL function, Python function and uniforms for this fractal.
        This method should only be called once for every Fractal object.

        :param compile_glsl if we should generate GLSL source or not (since we don't need that for audio)
        """
        if self._resolved:
            return
        assert not (self._attempted_resolve and not self._resolved), "The Fractal object may only make one resolve attempt."
        self._attempted_resolve = True

        try:
            self._ast = ast.parse(self._source, mode="exec", type_comments=True, feature_version=(3,11), filename="<Fractal Function>")
        except SyntaxError as err:
            raise CompilationError(f"Error occurred when parsing source: '{err}'", err=err) from None

        self.uniforms = []
        statements_without_uniform = []
        for stmt in self._ast.body:
            uni = FractalFunction._stripUniformFromStmt(stmt)
            if uni is not None:
                self.uniforms.append(uni)
            else:
                statements_without_uniform.append(stmt)
        self.uniforms = tuple(self.uniforms)
        self.updateUniforms()

        if compile_glsl:
            self._glsl_func_body = []
            variables = [("z", complex), ("c", complex), *self.uniforms]
            for stmt in statements_without_uniform:
                # noinspection PyTypeChecker
                self._glsl_func_body.append(FractalFunction._astToGLSL(stmt, variables)[0])
        self._glsl_func_body = tuple(self._glsl_func_body)

        py_func_ast = ast.Module()
        func_def = ast.FunctionDef()
        func_def.name = PY_FRACTAL_FUNC_NAME
        func_def.args = ast.arguments()
        func_def.args.args = [
            ast.arg(arg="z"),
            ast.arg(arg="c"),
            *[ast.arg(arg=u.name) for u in self.uniforms]
        ]
        func_def.body = statements_without_uniform
        py_func_ast.body = [func_def]

        func_def.args.posonlyargs = []
        func_def.args.kwonlyargs = []
        func_def.args.kw_defaults = []
        func_def.args.defaults = []
        func_def.decorator_list = []
        py_func_ast.type_ignores = []
        # noinspection PyTypeChecker
        ast.fix_missing_locations(py_func_ast)

        try:
            # noinspection PyTypeChecker
            code_obj = compile(py_func_ast, filename="<Fractal Function>", mode="exec", optimize=2)
        except SyntaxError as err:
            raise CompilationError(f"Error occurred when compiling source AST: '{err}'", err=err) from None

        namespace = FractalFunction._generateNameSpaceForExec()

        try:
            exec(code_obj, namespace)
            self.func = namespace[PY_FRACTAL_FUNC_NAME]
        except Exception as err:
            raise CompilationError(f"Error occurred when generating python function: '{err}'") from None

        self._resolved = True

    def updateUniforms(self):
        """Should be called every time any uniform value is changed. (this typically happens automatically)"""
        assert self.uniforms is not None
        self._uniform_dict = {u.name: u.value for u in self.uniforms}

    @property
    def uniformDict(self):
        assert self._uniform_dict is not None
        return self._uniform_dict

    def __call__(self, z, c):
        assert self.func is not None
        return self.func(z, c, **self._uniform_dict)

    def getGLSLFunc(self, pretty=False):
        """
        :return: the entire GLSL function source code of this fractal (including function definition).
        """
        assert self._resolved
        assert self._glsl_func_body is not None
        if not pretty:
            return f"VEC2 {GLSL_NAME_FORMAT % GLSL_FRACTAL_FUNC_NAME}(VEC2 z,VEC2 c){{{''.join(self._glsl_func_body)}}}"
        else:
            # TODO: actual prettying
            body = ["\t"+s+"\n" for s in self._glsl_func_body]
            return f"VEC2 {GLSL_NAME_FORMAT % GLSL_FRACTAL_FUNC_NAME}(VEC2 z, VEC2 c) {{\n{''.join(body)}}}"

    def getGLSLUniforms(self) -> Dict[str, _NumberAnyType]:
        """
        :return: a dict of all the GLSL uniform names and their values of this fractal.
        """
        assert self._resolved
        ...  # TODO

    def dumpJson(self) -> dict:
        assert self._resolved
        ...

    @staticmethod
    def loadJson(data: dict):
        ...

if __name__ == "__main__":
    frac = FractalFunction("""
return z ** 2 + c
    """)
    frac.resolve()
    print(frac.getGLSLFunc(True))
    print(frac(5, 1))

    exit()
    import objprint

    test_code = """
def f(self,z,c):
    return z**2+c
#a.imag = 0
# a: uniform(min=0, max=10, default=3)
#complex(1,2)
#z += +complex(1,2)
# z += (2+3j)
#z.imag += 2
#return z**2 + c
"""
    try:
        tree = ast.parse(test_code, mode="exec", filename="<TEST>")
        # print(ast.dump(tree, indent=2))
        print(objprint.op(tree))
        print("-" * 30)
        print(ast.unparse(tree))

        func = ast.FunctionDef()

    except SyntaxError as e:
        print(e)
        print(e.msg)
        print(e.text)
        print(e.lineno, e.offset)
        print(e.end_lineno, e.end_offset)

    ast.parse(test_code, mode="exec", type_comments=True)
