from random import randint, random, choice
from typing import Callable, Tuple, Any, Optional, Type


DEBUG_PRINT = True

class Op:
    def __init__(self, name: str, py_format_supplier: Callable, glsl_format_supplier: Callable, inputs: Tuple, outputs_supplier: Callable):
        self.name = name
        self._py_format_supplier = py_format_supplier
        self._glsl_format_supplier = glsl_format_supplier
        self._inputs = inputs
        self._outputs_supplier = outputs_supplier

    def matches(self, *input_types: Any):
        if len(input_types) != len(self._inputs):
            return False
        return all(issubclass(a, b) for a,b in zip(input_types, self._inputs))

    def getInputTypes(self):
        return self._inputs

    def getOutputType(self, *input_types: Any):
        return self._outputs_supplier(*input_types)

    # inputs eg.: ((complex, ("(a * b)", "cx_mul(a, b)")), ...)
    # returns: type and two expressions, one for python and one for glsl
    def apply(self, *inputs: Tuple[Any, Tuple[str, str]]) -> Optional[Tuple[Any, Tuple[str, str]]]:
        in_types = [i[0] for i in inputs]
        # if not self.matches(*in_types):
        #     return None
        params_py = tuple(i[1][0] for i in inputs)
        params_glsl = tuple(i[1][1] for i in inputs)
        return self.getOutputType(*in_types), (self._py_format_supplier(*in_types).format(*params_py), self._glsl_format_supplier(*in_types).format(*params_glsl))

    def __repr__(self):
        return self.name

sameAsIn = lambda t: t
cxOrFloat2In = lambda a,b: complex if (a is complex or b is complex) else float
def always(value):
    return lambda *_: value
def glslF2Cx(form: str):
    return lambda *ts: form.format(*((f"{{{i}}}" if t is complex else f"VEC2({{{i}}}, 0.)") for i,t in enumerate(ts)))
def twoForm(form_float: str, form_cx: str):
    return lambda t: form_cx if t is complex else form_float

OPERATIONS = (
    CREATE_CX := Op("cx", always("complex({0}, {1})"), always("VEC2({0}, {1})"), (float, float), always(complex)),
    RE := Op("re", always("{0}.real"), always("{0}.x"), (complex,), always(float)),
    IM := Op("re", always("{0}.imag"), always("{0}.y"), (complex,), always(float)),
    INVERSE := Op("inverse", always("(-{0})"), always("(-{0})"), (float | complex,), sameAsIn),
    ADD := Op("add", always("({0} + {1})"), always("({0} + {1})"), (float | complex, float | complex), cxOrFloat2In),
    SUB := Op("sub", always("({0} - {1})"), always("({0} - {1})"), (float | complex, float | complex), cxOrFloat2In),
    #TODO: improve mul and div
    MUL := Op("mul", always("({0} * {1})"), always("({0} * {1})"), (float, float), always(float)),
    MUL_CX := Op("mul_cx", always("({0} * {1})"), glslF2Cx("cx_mul({0}, {1})"), (complex, float | complex), always(complex)),
    DIV := Op("div", always("({0} / {1})"), always("({0} / {1})"), (float, float), always(float)),
    DIV_CX := Op("div_cx", always("({0} / {1})"), glslF2Cx("cx_div({0}, {1})"), (complex, float | complex), always(complex)),
    SQUARE := Op("square", always("({0} ** 2)"), twoForm("({0} * {0})", "cx_sqr({0})"), (float | complex,), sameAsIn),
    CUBE := Op("cube", always("({0} ** 3)"), twoForm("({0} * {0} * {0})", "cx_cube({0})"), (float | complex,), sameAsIn),
    EXP := Op("exp", always("(e ** ({0}))"), twoForm("expF({0})", "cx_exp({0})"), (float | complex,), sameAsIn),
    DOT := Op("dot", always("dot({0}, {1})"), always("dot({0}, {1})"), (complex, complex), always(float)),
    CIR_DOT := Op("cir_dot", always("cir_dot({0}, {1})"), always("({0} * {1})"), (complex, complex), always(complex)),
    SIN := Op("sin", always("sin({0})"), always("sinF({0})"), (float,), always(float)),
    COS := Op("cos", always("cos({0})"), always("cosF({0})"), (float,), always(float)),
    TAN := Op("tan", always("tan({0})"), always("tanF({0})"), (float,), always(float)),
)

def randomFloatValue(inputs: Tuple[Tuple[Any, Tuple[str, str]], ...]) -> Tuple[Tuple[Any, Tuple[str, str]], Optional[Op]]:
    if random() < .2:
        val = randint(0, 100) / 10
        return (float, ("%.1f" % val, "%.1f" % val)), None
    else:
        sym = choice(inputs)
        if sym[0] is float:
            return (float, (sym[1][0], sym[1][1])), None
        else:
            to_float_op = RE if random() < .5 else IM
            return to_float_op.apply(sym), to_float_op

def _debugPrintTree(value, depth: int):
    text = " " * depth * 2
    text += "└─"
    text += str(value)
    print(text)

# inputs eg.: (("a", complex), ("b", float), ...)
# returns: type and two expressions, one for python and one for glsl
def _gen(inputs: Tuple[Tuple[Type, Tuple[str, str]], ...], output_type: Any, complexity: float, next_complexity_mul: float, recursion_depth=0) -> Tuple[Any, Tuple[str, str]]:
    next_complexity = complexity * next_complexity_mul

    if random() > complexity:
        # Output float or complex
        while True:
            op = None
            if random() < .5:
                val = choice(inputs)
            else:
                val, op = randomFloatValue(inputs)
            if issubclass(val[0], output_type):
                if DEBUG_PRINT:
                    _debugPrintTree(val[1][0] if op is None else op, recursion_depth)
                return val
    else:
        # Output expression
        while True:
            op = choice(OPERATIONS)
            op_input_types = op.getInputTypes()
            op_inputs = []
            for t in op_input_types:
                op_inputs.append(_gen(inputs, t, next_complexity, next_complexity_mul, recursion_depth=recursion_depth+1))
            op_input_types = [i[0] for i in op_inputs]
            if not issubclass(op.getOutputType(*op_input_types), output_type):
                continue
            result = op.apply(*op_inputs)
            if result is not None:
                if DEBUG_PRINT:
                    _debugPrintTree(op, recursion_depth)
                return result

def genFractalExpression(initial_complexity: float, complexity_drop_off: float) -> Tuple[str, str]:
    _, exps = _gen(((complex, ("z", "z")), (complex, ("c", "c"))), complex, initial_complexity, complexity_drop_off)
    return exps

if __name__ == '__main__':
    for i in range(1):
        py_exp, glsl_exp = genFractalExpression(initial_complexity=1, complexity_drop_off=.9)
        print("Python: ", py_exp)
        print("GLSL: ", glsl_exp)
        print("-"*30)
