"""Plain-assert offline relay, capability and approval tests. No browser/network/model runs."""
import copy
import json
from pathlib import Path
import socket
import threading
import time
import ipaddress
import httpx
from email.message import Message
from unittest.mock import patch
import test_browser_search as h
import edge_tools as edge
import edge_work_browser as work

ORIGIN='chrome-extension://'+'a'*32


def paired():
    bridge=edge.Bridge();bridge.counter_base=1000000
    bridge.handle('/pair',{'tab':7,'url':'https://approved.example/','title':'Test page'},ORIGIN,'Bearer '+bridge.secret)
    return bridge


def refused(function,*args):
    try:function(*args)
    except (ValueError,RuntimeError):return
    raise AssertionError('must refuse')


def test_pair_requires_exact_secret_extension_origin_and_valid_url():
    bridge=edge.Bridge()
    for origin,secret in [('https://evil.example','Bearer '+bridge.secret),(ORIGIN,'Bearer wrong'),(ORIGIN,None)]:
        refused(bridge.handle,'/pair',{'tab':7,'url':'https://approved.example/','title':''},origin,secret)
    for url in ('file:///private','http://approved.example/','https://192.168.1.1/','https://user:pass@approved.example/'):
        refused(bridge.handle,'/pair',{'tab':7,'url':url,'title':''},ORIGIN,'Bearer '+bridge.secret)
    assert bridge.tab is None


def test_pair_is_one_use_bound_to_origin_and_tab():
    bridge=paired();auth='Bearer '+bridge.secret
    refused(bridge.handle,'/pair',{'tab':8,'url':'https://approved.example/','title':''},ORIGIN,auth)
    refused(bridge.handle,'/poll',{'tab':8},ORIGIN,auth)
    refused(bridge.handle,'/poll',{'tab':7},'chrome-extension://'+'b'*32,auth)
    assert bridge.handle('/poll',{'tab':7},ORIGIN,auth)=={'command':None}


def test_personal_bridge_cannot_queue_actions():
    bridge=paired()
    for action in ('click','type','scroll','open'):
        refused(bridge.rpc,'prepare',{'action':action})
    assert not bridge.pending


def test_rpc_matches_one_id_and_rejects_duplicate_and_unknown_results():
    bridge=paired();auth='Bearer '+bridge.secret;results=[]
    thread=threading.Thread(target=lambda:results.append(bridge.rpc('prepare',{'action':'read'})))
    thread.start()
    for _ in range(100):
        data=bridge.handle('/poll',{'tab':7},ORIGIN,auth)
        if data['command']:break
        time.sleep(.001)
    command=data['command'];assert command and command['args']['_base']==1000000
    refused(bridge.handle,'/result',{'id':'wrong','result':{}},ORIGIN,auth)
    bridge.handle('/result',{'id':command['id'],'result':{'ready':True}},ORIGIN,auth)
    refused(bridge.handle,'/result',{'id':command['id'],'result':{}},ORIGIN,auth)
    thread.join(2);assert not thread.is_alive() and results==[{'ready':True}]


def test_disconnect_revokes_secret_and_pending_commands():
    bridge=paired();old=bridge.secret;errors=[]
    def call():
        try:bridge.rpc('prepare',{'action':'read'})
        except ValueError:errors.append(True)
    thread=threading.Thread(target=call);thread.start();bridge.revoke();thread.join(2)
    assert not thread.is_alive() and errors and not bridge.pending and bridge.secret!=old
    refused(bridge.handle,'/poll',{'tab':7},ORIGIN,'Bearer '+old)


class Controller:
    def __init__(self):
        self.lock=threading.RLock();self.closed=False;self.tickets={};self.calls=[]
        self.preview={'action':'type','url':'https://approved.example/','control':'Search','text':'cats'}
        self.result={'dispatched':True}
    def rpc(self,op,args=None,stop=None):
        self.calls.append((op,copy.deepcopy(args)))
        if op=='prepare':return {'ticket':'r'*32,'preview':copy.deepcopy(self.preview)}
        return copy.deepcopy(self.result)


def test_prepare_validates_text_before_any_remote_command():
    controller=Controller()
    with patch.object(edge,'_current',return_value=controller):
        for text in ('','x'*501,'a@b','1234567','one\ntwo','one\ttwo'):
            assert 'error' in edge.prepare_edge('type',1,text)
    assert not controller.calls


def test_exact_preview_and_one_use_commit():
    controller=Controller()
    with patch.object(edge,'_current',return_value=controller),patch.object(edge.fetch,'safe_ip',return_value=None):
        proposal=edge.prepare_edge('type',1,'cats')
    assert proposal['preview']['text']=='cats' and 'token' in proposal
    assert edge.commit_edge(proposal['token']).startswith('Edge action dispatched')
    assert edge.commit_edge(proposal['token']).startswith('Error:')
    assert [name for name,_ in controller.calls]==['prepare','commit']


def test_changed_preview_dns_failure_and_bad_remote_ticket_refuse():
    for changes in ({'text':'changed'},{'url':'file:///secret'},{'destination':'https://192.168.1.1/'},{'action':'click'}):
        controller=Controller();controller.preview.update(changes)
        with patch.object(edge,'_current',return_value=controller),patch.object(edge.fetch,'safe_ip',return_value=None):
            assert 'error' in edge.prepare_edge('type',1,'cats')
    controller=Controller()
    with patch.object(edge,'_current',return_value=controller),patch.object(edge.fetch,'safe_ip',side_effect=ValueError('private DNS')):
        assert 'error' in edge.prepare_edge('type',1,'cats')


def test_stop_or_cancel_consumes_no_remote_action():
    controller=Controller();stop=threading.Event()
    with patch.object(edge,'_current',return_value=controller),patch.object(edge.fetch,'safe_ip',return_value=None):
        proposal=edge.prepare_edge('type',1,'cats')
    stop.set();assert edge.commit_edge(proposal['token'],stop).startswith('Error:')
    assert len(controller.calls)==1
    with patch.object(edge,'_current',return_value=controller),patch.object(edge.fetch,'safe_ip',return_value=None):
        proposal=edge.prepare_edge('type',1,'cats')
    edge.cancel_edge_pending()
    assert edge.commit_edge(proposal['token']).startswith('Error:') and len(controller.calls)==2


def test_read_size_cap_and_data_warning():
    controller=Controller();controller.preview={'action':'read','url':'https://approved.example/'}
    controller.result={'text':'page data'}
    with patch.object(edge,'_current',return_value=controller),patch.object(edge.fetch,'safe_ip',return_value=None):
        proposal=edge.prepare_edge('read')
    assert edge.commit_edge(proposal['token']).startswith(edge.PREFIX)
    controller.result={'text':'x'*3901}
    with patch.object(edge,'_current',return_value=controller),patch.object(edge.fetch,'safe_ip',return_value=None):
        proposal=edge.prepare_edge('read')
    assert edge.commit_edge(proposal['token']).startswith('Error:')


def run_core(calls,allow=True,after=None,result='Edge action dispatched'):
    rows=[];commits=[];prepared=[];messages=[]
    responses=iter([h.types.SimpleNamespace(message=h.types.SimpleNamespace(content='',tool_calls=calls)),
                    h.types.SimpleNamespace(message=h.types.SimpleNamespace(content='Done',tool_calls=[]))])
    def prepare(action,element,text,stop):
        prepared.append((action,element,text));return {'token':'private-ticket','preview':{'action':action,'url':'https://approved.example/','text':text}}
    def ask(name,args):
        rows.append((name,copy.deepcopy(args)))
        if after:after(name,args)
        return allow
    def commit(token,stop):commits.append(token);return result
    with patch.object(h.core,'chat',side_effect=lambda **kw:next(responses)),patch.object(h.core,'compact',return_value=False), \
         patch.object(h.core,'prepare_edge',side_effect=prepare),patch.object(h.core,'commit_edge',side_effect=commit), \
         patch.object(h.core,'audit'),patch.object(h.core,'edge_available',return_value=True),patch.object(h.core,'work_available',return_value=True):
        answer,_=h.core.run_turn(messages,'Use my work Edge tab',ask,log=lambda s:None)
    return h.types.SimpleNamespace(popups=rows,commits=commits,prepared=prepared,messages=messages,answer=answer)


def test_model_cannot_supply_urls_tickets_selectors_or_approval_flags_to_actions():
    for args in ({'element':1,'url':'https://evil.example/'},{'element':1,'approved':True},
                 {'element':1,'ticket':'x'},{'element':True},{'selector':'button'}):
        result=run_core([h.tool_call('edge_click',args)])
        assert not result.prepared and not result.commits and not result.popups


def test_every_edge_action_has_own_popup_even_in_plan():
    calls=[h.tool_call('propose_plan',{'goal':'Read','steps':['open https://approved.example/']}),
           h.tool_call('edge_read',{}),h.tool_call('edge_type',{'element':1,'text':'cats'})]
    result=run_core(calls)
    assert [name for name,_ in result.popups]==['plan','edge_operation','edge_operation']
    assert len(result.commits)==2


def test_denial_pauses_and_discards_remaining_batch():
    result=run_core([h.tool_call('edge_read',{}),h.tool_call('edge_click',{'element':1})],allow=False)
    assert not result.commits and len(result.prepared)==1 and 'paused' in result.answer
    assert any('queued action not run' in m.get('content','') for m in result.messages if isinstance(m,dict))


def test_approval_mutation_cannot_change_prepared_action():
    def mutate(name,args):args['text']='CHANGED';args['url']='https://evil.example/'
    result=run_core([h.tool_call('edge_type',{'element':1,'text':'cats'})],after=mutate)
    assert result.prepared==[('type',1,'cats')] and result.commits==['private-ticket']


def test_schemas_absent_until_person_starts_or_pairs_relevant_mode():
    with patch.object(h.core,'edge_available',return_value=False),patch.object(h.core,'work_available',return_value=False):
        names={f.__name__ for f in h.core.offered_tools('hi')}
        assert not names & h.core.EDGE_TOOLS
    with patch.object(h.core,'edge_available',return_value=True),patch.object(h.core,'work_available',return_value=False):
        names={f.__name__ for f in h.core.offered_tools('hi')}
        assert h.core.EDGE_SHARED<=names and not names & h.core.EDGE_WORK


def test_profile_scope_and_resume_reads_are_separate():
    assert work.PROFILE.name=='edge_work_profile'
    assert 'edge_work_profile/' in (Path(__file__).parent/'.gitignore').read_text()
    evidence=h.core.TurnEvidence(resume=True)
    assert evidence.problem('edge_click',{'element':1})
    evidence.result('edge_read',edge.PREFIX+'\npage')
    assert not evidence.problem('edge_click',{'element':1})
    evidence.result('edge_click','Edge action dispatched')
    assert evidence.problem('edge_click',{'element':1})


def test_extension_permissions_and_personal_mode_are_narrow():
    folder=Path(__file__).parent/'edge_extension'
    manifest=json.loads((folder/'manifest.json').read_text())
    assert set(manifest['permissions'])=={'activeTab','scripting'}
    assert manifest['host_permissions']==['http://127.0.0.1/*']
    assert '<all_urls>' not in json.dumps(manifest)
    assert "!['read','copy'].includes" in (folder/'panel.js').read_text()
    assert 'localStorage' not in (folder/'panel.js').read_text()
    assert 'innerHTML' not in (folder/'panel.js').read_text()


def routed(method='GET',body=None,status=200,headers=None,data=b'<h1>Hello</h1>',active=False):
    controller=object.__new__(work.WorkBrowser)
    controller.request_count=0;controller.response_bytes=0
    controller.blocked_requests=0;controller.post_origin=('https','approved.example')
    controller.allow_posts_until=time.monotonic()+5 if active else 0
    class Route:
        def __init__(self):
            self.request=h.types.SimpleNamespace(url='https://approved.example/page',method=method,
                post_data_buffer=body,all_headers=lambda:{'Cookie':'synthetic=one','Host':'untrusted','Accept-Encoding':'gzip'})
            self.aborted=False;self.fulfilled=None
        def abort(self,reason):self.aborted=True
        def fulfill(self,**args):self.fulfilled=args
        def continue_(self):raise AssertionError('Chromium must not do DNS or direct fetching')
    route=Route();calls=[];real_client=httpx.Client
    class Stream(httpx.SyncByteStream):
        def __iter__(self):yield data
    def network(request):
        calls.append(request)
        return httpx.Response(status,headers=headers or {'content-type':'text/html'},stream=Stream())
    def client(**options):
        assert options['follow_redirects'] is False and options['trust_env'] is False and options['timeout']==10
        return real_client(transport=httpx.MockTransport(network),**options)
    with patch.object(work.fetch,'safe_ip',return_value=ipaddress.ip_address('93.184.216.34')) as dns, \
         patch.object(work.httpx,'Client',side_effect=client):
        controller.route(route)
    return route,calls,dns.call_count


def test_work_network_pins_ip_and_forwards_only_work_cookie_identity():
    route,calls,dns=routed()
    assert not route.aborted and route.fulfilled and dns==1 and len(calls)==1
    request=calls[0]
    assert request.url.host=='93.184.216.34' and request.headers['Host']=='approved.example'
    assert request.extensions['sni_hostname']=='approved.example'
    assert request.headers['Cookie']=='synthetic=one' and request.headers['Accept-Encoding']=='identity'


def test_work_post_requires_recent_approved_action_and_has_body_cap():
    for method,body,active in [('POST',b'q=cats',False),('PUT',b'x',True),('POST',b'x'*256001,True)]:
        route,calls,dns=routed(method=method,body=body,active=active)
        assert route.aborted and not calls and dns==0
    route,calls,dns=routed(method='POST',body=b'q=cats',active=True)
    assert route.fulfilled and calls[0].content==b'q=cats'


def test_work_redirect_attachment_encoding_and_size_fail_closed():
    for options in ({'status':302,'headers':{'location':'https://192.168.1.1/'}},
                    {'headers':{'content-disposition':'attachment; filename=secret.txt'}},
                    {'headers':{'content-encoding':'gzip'}},
                    {'headers':{'content-length':'5000001'}}, {'data':b'x'*5000001}):
        route,calls,_=routed(**options)
        assert route.aborted and not route.fulfilled


def test_loopback_transport_rejects_web_origins_wrong_host_and_chunked_body():
    handler_type=edge._handler(edge.Bridge())
    def handler(host='127.0.0.1:3333',origin=ORIGIN,encoding=None,client='127.0.0.1'):
        instance=object.__new__(handler_type)
        instance.headers=Message();instance.headers['Host']=host;instance.headers['Origin']=origin
        if encoding:instance.headers['Transfer-Encoding']=encoding
        instance.server=h.types.SimpleNamespace(server_port=3333);instance.client_address=(client,1234)
        return instance
    assert handler().valid_transport()
    for instance in (handler(host='localhost:3333'),handler(origin='https://evil.example'),
                     handler(encoding='chunked'),handler(client='192.168.1.2')):
        assert not instance.valid_transport()


def test_shared_handoff_copies_exact_url_into_work_with_no_cookie_payload():
    source=Controller();target=Controller()
    source.preview={'action':'copy','url':'https://approved.example/exact?q=cats'}
    source.result={'url':source.preview['url']}
    with patch.object(edge,'_current',return_value=source),patch.object(work,'work_current',return_value=target), \
         patch.object(edge.fetch,'safe_ip',return_value=None):
        proposal=edge.prepare_edge('open_shared')
        assert 'token' in proposal
        result=edge.commit_edge(proposal['token'])
    assert result.startswith('Opened the approved shared address')
    assert target.calls==[('navigate',{'url':'https://approved.example/exact?q=cats'})]


def test_shared_handoff_into_isolated_browser_uses_approved_url_and_reads_it():
    url='https://approved.example/exact?q=cats'
    with patch.object(h.core,'browser_open',return_value='Page opened.') as opener, \
         patch.object(h.core,'browser_read',return_value='[Web page text below.]\nFixture data') as reader:
        result=run_core([h.tool_call('edge_copy_to_browser',{})],result='URL '+url)
    assert result.commits==['private-ticket']
    opener.assert_called_once_with(url);reader.assert_called_once_with()


if __name__=='__main__':
    assert __debug__
    tests=[v for k,v in sorted(globals().items()) if k.startswith('test_')]
    with patch.object(socket,'socket',side_effect=h.no_external_call),patch.object(socket,'getaddrinfo',side_effect=h.no_external_call):
        for test in tests:
            try:test()
            finally:edge.cancel_edge_pending()
            print('PASS',test.__name__)
    print(f'All {len(tests)} offline Edge tests passed.')
