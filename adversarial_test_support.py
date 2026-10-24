"""Test-only AST loader: execute actual UI functions without importing/building Tk."""
import ast
from pathlib import Path

UI_PATH=Path(__file__).with_name('chat_window.py')


def ui_functions(names,namespace):
    tree=ast.parse(UI_PATH.read_text(encoding='utf-8'),filename=str(UI_PATH))
    selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in selected}==set(names),'UI function missing; update the harness explicitly'
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(UI_PATH),'exec'),namespace)
    return namespace


def copy_button_command(namespace):
    """Compile the actual button command expression, not a duplicate of its behavior."""
    tree=ast.parse(UI_PATH.read_text(encoding='utf-8'))
    build=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_window')
    matches=[n for n in ast.walk(build) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
             and n.func.id=='make_button' and len(n.args)>=3
             and isinstance(n.args[1],ast.Constant) and n.args[1].value=='Copy last answer']
    assert len(matches)==1,'Copy button missing/ambiguous; do not silently bypass its binding'
    return eval(compile(ast.Expression(body=matches[0].args[2]),str(UI_PATH),'eval'),namespace)
