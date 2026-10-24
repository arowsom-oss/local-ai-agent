"""Negative controls: temporarily remove gates IN MEMORY; unchanged tests must catch them.

Never edits application source. These are test-sensitivity results, not application passes.
"""
import argparse
import ast
import inspect
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import test_feature_adversarial as tests
import test_browser_search as h


def mutant(function,change):
    tree=ast.parse(inspect.getsource(function));changed=[]
    class Edit(ast.NodeTransformer):
        def visit(self,node):
            result=change(node)
            if result is not node:changed.append(True);return result
            return super().visit(node)
    tree=Edit().visit(tree);ast.fix_missing_locations(tree)
    assert len(changed)==1,f'Mutation must identify exactly one gate, got {len(changed)}'
    namespace=dict(function.__globals__)
    exec(compile(tree,inspect.getsourcefile(function),'exec'),namespace)
    return namespace[function.__name__]


def remove_refusal(function,message):
    def change(node):
        if isinstance(node,ast.If) and any(isinstance(n,ast.Raise) and message in ast.unparse(n) for n in node.body):
            return None
        return node
    return mutant(function,change)


def keyword(function,name,value):
    def change(node):
        if isinstance(node,ast.keyword) and node.arg==name:return ast.keyword(arg=name,value=ast.Constant(value))
        return node
    return mutant(function,change)


def main():
    assert __debug__,'Run without -O'
    parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
    if args.report.exists():raise RuntimeError('Refusing to overwrite sensitivity evidence')
    cases=[
      ('Q&A tool-output refusal',tests.qa,'ask',remove_refusal(tests.qa.ask,'Document Q&A refuses action/tool output'),
       tests.test_poisoned_text_file_and_model_following_injection_cannot_request_actions),
      ('Q&A quote membership',tests.qa,'validate_answer',remove_refusal(tests.qa.validate_answer,'Supporting quote does not match'),
       tests.test_quote_absent_from_actual_selected_file_is_refused_even_with_valid_citation_id),
      ('Saved transcript role/schema gate',tests.saved,'transcript_text',remove_refusal(tests.saved.transcript_text,'Only user/assistant text'),
       tests.test_saved_snapshots_cannot_store_authority_roles_tool_protocol_or_permission_fields),
      ('Saved snapshot authority-field gate',tests.saved,'decode_snapshot',remove_refusal(tests.saved.decode_snapshot,'Unsupported saved chat format'),
       tests.test_saved_snapshots_cannot_store_authority_roles_tool_protocol_or_permission_fields),
      ('Reopen permission revocation',h.core,'forget_sites',lambda:None,
       tests.test_reopened_poisoned_chat_revokes_live_authority_and_requires_a_new_site_popup),
      ('ZIP input byte cap',tests.archive,'unpack',remove_refusal(tests.archive.unpack,'Invalid ZIP chat payload'),
       tests.test_oversized_zip_container_is_rejected_before_zip_parser_runs),
      ('HTML script reduction',tests.web,'_DROP',tests.web._DROP-{'script'},
       tests.test_html_reducer_removes_script_event_handlers_navigation_and_external_targets),
      ('HTML disabled JavaScript',tests.web,'render_document',keyword(tests.web.render_document,'java_script_enabled',True),
       tests.test_html_browser_has_independent_no_script_no_network_policy_and_csp),
      ('HTML offline context',tests.web,'render_document',keyword(tests.web.render_document,'offline',False),
       tests.test_html_browser_has_independent_no_script_no_network_policy_and_csp),
      ('HTML CSP',tests.web,'CSP','',tests.test_html_browser_has_independent_no_script_no_network_policy_and_csp),
      ('HTML navigation postcondition',tests.web,'render_document',remove_refusal(tests.web.render_document,'Preview navigation changed unexpectedly'),
       tests.test_html_unexpected_navigation_is_refused_and_browser_closed),
    ]
    def member_name(node):
        if isinstance(node,ast.Compare) and ast.unparse(node)=='info.filename != MEMBER':return ast.Constant(False)
        return node
    cases.append(('ZIP fixed member name',tests.archive,'unpack',mutant(tests.archive.unpack,member_name),
                  tests.test_zip_traversal_absolute_encoded_and_windows_member_names_refuse_before_open))
    def expansion(node):
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Not) and 'info.file_size' in ast.unparse(node):return ast.Constant(False)
        return node
    cases.append(('ZIP declared expansion cap',tests.archive,'unpack',mutant(tests.archive.unpack,expansion),
                  tests.test_zip_declared_expansion_over_limit_is_rejected_before_decompression))
    def unbounded_read(node):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='read':
            return ast.Call(func=node.func,args=[],keywords=[])
        return node
    cases.append(('ZIP bounded inflate read',tests.archive,'unpack',mutant(tests.archive.unpack,unbounded_read),
                  tests.test_zip_stream_is_bounded_even_if_member_metadata_lies))
    def route_allow(node):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='abort':
            return ast.Call(func=ast.Attribute(value=node.func.value,attr='fulfill',ctx=ast.Load()),args=[],
                keywords=[ast.keyword(arg='status',value=ast.Constant(200)),ast.keyword(arg='body',value=ast.Name(id='document',ctx=ast.Load()))])
        return node
    cases.append(('HTML abort unauthorized routes',tests.web,'render_document',mutant(tests.web.render_document,route_allow),
                  tests.test_html_routes_block_external_subresources_second_navigation_post_and_child_frames))
    rows=[]
    for name,module,attribute,replacement,test in cases:
        with patch.object(module,attribute,replacement):
            try:test()
            except AssertionError as exc:row=dict(gate=name,detected=True,assertion=str(exc)[:250])
            except Exception as exc:row=dict(gate=name,detected=False,harness_error=type(exc).__name__+': '+str(exc)[:200])
            else:row=dict(gate=name,detected=False,error='Weakened gate escaped the adversarial assertion')
        rows.append(row);print(('DETECTED ' if row['detected'] else 'MISSED ')+name,flush=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    print(f"{sum(r['detected'] for r in rows)}/{len(rows)} in-memory removed gates detected.")
    return int(not all(r['detected'] for r in rows))


if __name__=='__main__':raise SystemExit(main())
