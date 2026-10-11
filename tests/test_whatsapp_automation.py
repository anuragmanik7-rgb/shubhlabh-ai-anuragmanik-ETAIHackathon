"""WhatsApp automation (n8n workflow, Twilio Studio flow): JSON replies, the relay token (header or Basic auth), async replies,
the plan lane (text -> one-click campaign -> WhatsApp summary -> signed printable brief), STOP and status, limits, and the
integration files themselves. The Studio flow is run by a small interpreter against the real API. Offline, no paid calls."""
import base64, hashlib, hmac, json, re, shutil, subprocess, time
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from backend.app import festivals, whatsapp as W, whatsapp_plan as P
from backend.app.domain import now, uid
from backend.app.main import create_app
from backend.app.persistence import Store

ROOT = Path(__file__).resolve().parents[1]
N8N = ROOT / 'integrations' / 'n8n' / 'shubhlabh_whatsapp_twilio_full.json'
STUDIO = ROOT / 'integrations' / 'twilio' / 'shubhlabh_whatsapp_studio_flow.json'
PHONE = 'whatsapp:+919876500001'
RELAY = 'relay-secret-for-tests'
H = {'X-Relay-Token': RELAY}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    for k in ('TWILIO_AUTH_TOKEN', 'WHATSAPP_WEBHOOK_URL', 'TWILIO_ACCOUNT_SID', 'PUBLIC_BASE_URL'):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv('WHATSAPP_RELAY_TOKEN', RELAY)
    return TestClient(create_app(f"sqlite:///{tmp_path/'auto.sqlite3'}"))


@pytest.fixture()
def store(tmp_path):
    return Store(f"sqlite:///{tmp_path/'unit.sqlite3'}")


def ask(client, body, phone=PHONE, **data):
    return client.post('/api/v2/whatsapp/inbound?format=json', data={'From': phone, 'Body': body, **data}, headers=H).json()


def wait_plan(client, cid, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        v = client.get(f'/api/v2/whatsapp/plan/{cid}?wait=9', headers=H).json()
        if v['status'] != 'running':
            return v
    raise AssertionError('plan did not finish')


# ---------------------------------------------------------------- JSON mode and relay auth
def test_json_mode_by_query_or_accept_header_and_twiml_stays_the_default(client):
    r = client.post('/api/v2/whatsapp/inbound?format=json', data={'From': PHONE, 'Body': 'Maggi MRP 14 sell 15'}, headers=H)
    assert r.status_code == 200 and r.headers['content-type'].startswith('application/json')
    j = r.json()
    assert j['status'] == 'done' and j['intent'] == 'offer_check' and 'above MRP' in j['reply']
    assert client.post('/api/v2/whatsapp/inbound', data={'From': PHONE, 'Body': 'Diwali'},
                       headers={**H, 'Accept': 'application/json'}).json()['intent'] == 'festival'
    old = client.post('/api/v2/whatsapp/inbound', data={'From': PHONE, 'Body': 'Diwali'}, headers=H)  # the old n8n relay
    assert old.headers['content-type'].startswith('application/xml') and '<Message>' in old.text


def test_twilio_signed_requests_get_twiml_even_when_they_accept_json(client, monkeypatch):
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'test-token')
    params = {'From': PHONE, 'Body': 'Diwali', 'NumMedia': '0'}
    sig = W.twilio_signature('http://testserver/api/v2/whatsapp/inbound', params, 'test-token')
    r = client.post('/api/v2/whatsapp/inbound', data=params, headers={'X-Twilio-Signature': sig, 'Accept': 'application/json'})
    assert r.status_code == 200 and r.headers['content-type'].startswith('application/xml')


def test_basic_auth_carries_the_relay_token_for_twilio_studio(client):
    ok = client.post('/api/v2/whatsapp/inbound?format=json', data={'From': PHONE, 'Body': 'Holi'}, auth=('relay', RELAY))
    assert ok.status_code == 200 and ok.json()['intent'] == 'festival'
    bad = 'Basic ' + base64.b64encode(b'relay:wrong').decode()
    assert client.post('/api/v2/whatsapp/inbound?format=json', data={'From': PHONE, 'Body': 'hi'}, headers={'Authorization': bad}).status_code == 403
    assert client.post('/api/v2/whatsapp/inbound?format=json', data={'From': PHONE, 'Body': 'hi'}).status_code == 403
    # an HTTP widget that sends the fields as query parameters works too (relay only)
    q = client.post('/api/v2/whatsapp/inbound', params={'format': 'json', 'From': PHONE, 'Body': 'Holi'}, headers=H)
    assert q.json()['intent'] == 'festival'


def test_errors_still_answer_in_json(client, monkeypatch):
    monkeypatch.setattr(W, 'handle', lambda *a, **k: 1 / 0)
    j = ask(client, 'hi')
    assert j['intent'] == 'error' and j['reply'].startswith('🙏')


# ---------------------------------------------------------------- async replies and media
def test_slow_replies_come_back_as_a_job_to_poll(client, monkeypatch):
    real = W.handle

    def slow(*a, **k):
        time.sleep(1.0)
        return real(*a, **k)
    monkeypatch.setattr(W, 'handle', slow)
    r = client.post('/api/v2/whatsapp/inbound?format=json&wait=0.2', data={'From': PHONE, 'Body': 'Diwali'}, headers=H).json()
    assert r['status'] == 'pending' and r['intent'] == 'pending' and re.fullmatch(r'wajob_[0-9a-f]{16}', r['job_id'])
    assert 'reading the prices' in r['reply']
    assert client.get(f"/api/v2/whatsapp/jobs/{r['job_id']}").status_code == 403  # relay only
    done = client.get(f"/api/v2/whatsapp/jobs/{r['job_id']}?wait=9", headers=H).json()
    assert done['status'] == 'done' and done['intent'] == 'festival' and 'Diwali' in done['reply']
    fast = client.post('/api/v2/whatsapp/inbound?format=json&wait=5', data={'From': PHONE, 'Body': 'Holi'}, headers=H).json()
    assert fast['status'] == 'done' and fast['intent'] == 'festival'
    assert client.get('/api/v2/whatsapp/jobs/not-a-job', headers=H).status_code == 404


def test_media_type_is_sniffed_when_missing_and_voice_notes_are_not_downloaded(client, monkeypatch):
    img = (ROOT / 'evidence-set' / 'synthetic' / 'shelf_tag_03.jpg').read_bytes()
    calls = []
    monkeypatch.setattr(W, 'fetch_media', lambda url: calls.append(url) or img)
    media = 'https://api.twilio.com/2010-04-01/Accounts/AC1/Messages/MM1/Media/ME1'
    assert ask(client, '', NumMedia='1', MediaUrl0=media)['intent'] == 'photo' and calls == [media]
    assert ask(client, '', NumMedia='1', MediaUrl0=media, MediaContentType0='audio/ogg')['intent'] == 'help' and len(calls) == 1
    assert W.sniff(b'%PDF-1.7') == 'application/pdf' and W.sniff(b'\x89PNG\r\n\x1a\n0000') == 'image/png' and W.sniff(b'GIF89a') == ''


# ---------------------------------------------------------------- the plan lane
def test_plan_text_is_parsed_with_festival_template_defaults():
    today = date(2026, 10, 10)
    inputs, assumed = P.parse('plan', today)
    assert inputs == {'festival_id': 'navratri', 'budget_paise': 3_000_000, 'cities': ['Bengaluru', 'Mumbai', 'Delhi'], 'goal': 'profit'}
    assert set(assumed) == {'festival', 'budget', 'cities', 'goal'}
    assert P.parse('Diwali plan budget 40k Delhi clearance', today) == (
        {'festival_id': 'diwali', 'budget_paise': 4_000_000, 'cities': ['Delhi'], 'goal': 'clearance'}, [])
    holi, _ = P.parse('Holi campaign ₹1.5 lakh Bangalore aur Mumbai, play safe', today)
    assert holi == {'festival_id': 'holi', 'budget_paise': 15_000_000, 'cities': ['Bengaluru', 'Mumbai'], 'goal': 'conservative'}
    kc, assumed = P.parse('Karwa Chauth plan', today)
    assert kc['cities'] == ['Delhi'] and 'cities' in assumed                  # the template's own cities
    assert P.parse('plan budget 50', today)[0]['budget_paise'] == P.BUDGET_MIN
    assert P.parse('Diwali plan 25,000 ka budget', today)[0]['budget_paise'] == 2_500_000
    assert P.parse('plan for the holidays', today)[0]['festival_id'] == 'navratri'  # "holidays" is not Holi
    assert P.next_festival(date(2026, 10, 12))['id'] == 'dussehra'


def test_plan_lane_end_to_end_with_summary_and_printable_brief(client, monkeypatch, tmp_path):
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://shubhlabh.example')
    s = client.post('/api/v2/whatsapp/plan', json={'From': PHONE, 'Body': 'Diwali plan budget 40000 Delhi'}, headers=H).json()
    assert s['status'] == 'started' and re.fullmatch(r'camp_[0-9a-f]{16}', s['campaign_id'])
    assert 'Planning your Diwali campaign' in s['ack'] and 'about 2 minutes' in s['ack'] and '₹40,000' in s['ack']
    assert 'Send *status*' in s['timeout_text'] and s['sorry_text'].startswith('🙏')
    again = client.post('/api/v2/whatsapp/plan', data={'From': PHONE, 'Body': 'Diwali plan'}, headers=H).json()  # a form body works too
    assert again['status'] == 'already_running' and again['campaign_id'] == s['campaign_id']
    assert client.get(f"/api/v2/whatsapp/plan/{s['campaign_id']}").status_code == 403  # relay only
    v = wait_plan(client, s['campaign_id'])
    assert v['status'] == 'ready', v
    text = v['summary']
    for must in ('Your Diwali plan is ready', '6–8 Nov', "verified by ShubhLabh's Intelli AI", 'Top offers',
                 "estimated on ShubhLabh's reference store data", 'Worst case', 'of your ₹40,000 budget',
                 'Nothing goes live until you approve', 'Printable brief'):
        assert must in text, must
    assert len(text) <= W.MAX_REPLY and not re.search(r"synthetic|instant|india's first|by code|\bdemo\b|simulat", text, re.I)
    assert v['link'] in text  # never truncated away
    assert v['link'].startswith('https://shubhlabh.example/api/v2/whatsapp/brief/' + s['campaign_id'] + '?sig=')
    path = v['link'][len('https://shubhlabh.example'):]
    page = client.get(path)
    assert page.status_code == 200 and page.headers['content-type'].startswith('text/html')
    assert 'campaign brief' in page.text and "Estimated on ShubhLabh's reference store data" in page.text and '<script' not in page.text.lower()
    assert "Offers verified by ShubhLabh's Intelli AI" in page.text and not re.search(r'certified|by code|\bdemo\b|simulat', page.text, re.I)
    assert client.get(path.split('?')[0] + '?sig=' + '0' * 32).status_code == 404
    st = ask(client, 'status')
    assert st['intent'] == 'status' and 'Your Diwali plan is ready' in st['reply']
    assert b'9876500001' not in b''.join(p.read_bytes() for p in tmp_path.glob('auto.sqlite3*'))  # never the number
    assert client.get('/api/v2/whatsapp/plan/camp_0000000000000000', headers=H).status_code == 404
    assert client.get('/api/v2/whatsapp/plan/../../x', headers=H).status_code == 404


def test_stop_after_asking_means_the_plan_is_not_sent(client):
    phone = 'whatsapp:+919876500002'
    s = client.post('/api/v2/whatsapp/plan', json={'From': phone, 'Body': 'Holi plan'}, headers=H).json()
    assert ask(client, 'STOP', phone)['intent'] == 'stop'
    v = client.get(f"/api/v2/whatsapp/plan/{s['campaign_id']}?wait=1", headers=H).json()
    assert v['status'] == 'cancelled' and v['summary'] is None


def test_plan_needs_the_relay_token_and_a_sender(client, monkeypatch):
    assert client.post('/api/v2/whatsapp/plan', json={'From': PHONE, 'Body': 'plan'}).status_code == 403
    assert client.post('/api/v2/whatsapp/plan', json={'Body': 'plan'}, headers=H).status_code == 400
    monkeypatch.delenv('WHATSAPP_RELAY_TOKEN')
    assert client.post('/api/v2/whatsapp/plan', json={'From': PHONE, 'Body': 'plan'}, headers=H).status_code == 503


def _fake_campaign(status):
    def start(store, tenant, inputs, files, background=True):
        f = festivals.get(inputs['festival_id'])
        rec = {'id': uid('camp_'), 'created_at': now(), 'status': status, 'inputs': inputs, 'steps': [],
               'festival': {k: f[k] for k in ('id', 'name', 'start', 'end', 'tagline', 'palette')}, 'error': None}
        store.put_new(tenant, 'campaign', rec['id'], rec)
        return rec
    return start


def test_plan_limits_per_sender(store, monkeypatch):
    monkeypatch.setattr(P.campaign, 'start', _fake_campaign('failed'))
    monkeypatch.setattr(P, 'ensure_seed', lambda store, tenant: None)
    for _ in range(P.PLAN_HOURLY_LIMIT):
        assert P.start(store, PHONE, 'Diwali plan')['status'] == 'started'
    r = P.start(store, PHONE, 'Diwali plan')
    assert r['status'] == 'plan_limit' and r['campaign_id'] is None and '*status*' in r['ack']
    other = 'whatsapp:+919876500003'
    for _ in range(W.HOURLY_LIMIT):
        W._rate_ok(store, W.sender_id(other))
    assert P.start(store, other, 'Diwali plan')['status'] == 'rate_limited'
    failed = P.view(store, P.start(store, 'whatsapp:+919876500004', 'Holi plan')['campaign_id'])
    assert failed['status'] == 'failed' and 'Holi plan' in failed['summary'] and failed['link'] is None


def test_greeting_with_a_request_and_status_without_a_plan(store):
    hi = lambda text: W.handle(store, PHONE, text, use_model=False, today=date(2026, 10, 10))  # noqa: E731
    assert hi('Hi')['intent'] == 'help'
    assert hi('Hi, Diwali')['intent'] == 'festival'
    assert hi('Hello, Diwali plan')['intent'] == 'plan'
    st = hi('status')
    assert st['intent'] == 'status' and "don't have a plan yet" in st['reply']
    assert hi('Happy holidays')['intent'] == 'help'  # not Holi


# ---------------------------------------------------------------- the integration files
def test_n8n_workflow_is_complete_and_holds_no_secrets():
    raw = N8N.read_text(encoding='utf-8')
    wf = json.loads(raw)
    names = [n['name'] for n in wf['nodes']]
    assert len(names) == len(set(names)) and len({n['id'] for n in wf['nodes']}) == len(names)
    for src, outs in wf['connections'].items():
        assert src in names
        assert all(c['node'] in names for branch in outs['main'] for c in branch)
    by_type = {}
    for n in wf['nodes']:
        by_type.setdefault(n['type'], []).append(n)
    hook = by_type['n8n-nodes-base.webhook'][0]['parameters']
    assert hook['httpMethod'] == 'POST' and hook['responseMode'] == 'responseNode'
    assert any(n['parameters'].get('responseBody') == '<Response/>' for n in by_type['n8n-nodes-base.respondToWebhook'])
    assert len(by_type['n8n-nodes-base.twilio']) >= 6 and all(n['parameters']['toWhatsapp'] is True for n in by_type['n8n-nodes-base.twilio'])
    assert all(n.get('disabled') is True and 'optional' in n['name'].lower() for n in by_type['n8n-nodes-base.googleSheets'])
    assert by_type['n8n-nodes-base.errorTrigger'] and by_type['n8n-nodes-base.wait'] and by_type['n8n-nodes-base.stickyNote']
    # paste-and-go: no server environment variables or builtin modules, one Settings node holds everything
    assert '$env.' not in raw and 'require(' not in raw
    settings = next(n for n in wf['nodes'] if n['name'] == 'Settings')
    vals = {a['name']: a['value'] for a in settings['parameters']['assignments']['assignments']}
    assert set(vals) >= {'shubhlabh_url', 'relay_token', 'twilio_whatsapp_from', 'twilio_auth_token', 'webhook_public_url'}
    assert vals['twilio_auth_token'] == '' and vals['relay_token'].startswith('PASTE-')  # the committed copy holds no secret
    assert wf['connections']['Twilio WhatsApp message in']['main'][0][0]['node'] == 'Settings'
    assert 'x-twilio-signature' in raw and 'function hmacSha1' in raw
    assert len({json.dumps(n['credentials'], sort_keys=True) for n in by_type['n8n-nodes-base.twilio']}) == 1  # one Twilio credential
    assert '/api/v2/whatsapp/plan' in raw and '/api/v2/whatsapp/inbound?format=json' in raw
    assert not re.search(r'AC[0-9a-f]{32}|SK[0-9a-f]{32}', raw)


def _run_n8n_code(tmp_path, js, outputs):
    """Runs an n8n Code node body with node.js, with $('Node').first().json answered from `outputs`."""
    node = shutil.which('node')
    if not node:
        pytest.skip('node.js is not installed')
    harness = tmp_path / 'node_harness.js'
    harness.write_text('const OUT = ' + json.dumps(outputs, ensure_ascii=False) + ';\n'
                       'const $ = (n) => ({ first: () => ({ json: OUT[n] }) });\n'
                       'const $input = { first: () => ({ json: {} }) };\nconst $runIndex = 0;\n'
                       'const run = () => {\n' + js + '\n};\nprocess.stdout.write(JSON.stringify(run()));\n', encoding='utf-8')
    r = subprocess.run([node, str(harness)], capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)[0]['json']


def test_n8n_code_nodes_run_without_server_settings(tmp_path):
    """The signature check and the classifier are plain JavaScript (no require, no $env): run them with node.js."""
    wf = json.loads(N8N.read_text(encoding='utf-8'))
    code = {n['name']: n['parameters'].get('jsCode') for n in wf['nodes']}
    path = next(n for n in wf['nodes'] if n['type'] == 'n8n-nodes-base.webhook')['parameters']['path']
    url = 'https://n8n.example.com/webhook/' + path
    params = {'From': 'whatsapp:+919800012345', 'Body': 'Atta 5kg MRP 280 sell 250 cost 230 ₹ नमस्ते 🙏', 'To': 'whatsapp:+14155238886',
              'NumMedia': '0', 'ProfileName': 'Ramesh'}
    token = 'test-auth-token-0123456789abcdef'
    sig = base64.b64encode(hmac.new(token.encode(), (url + ''.join(k + params[k] for k in sorted(params))).encode(), hashlib.sha1).digest()).decode()

    def verify(settings, headers, webhook_url=''):
        return _run_n8n_code(tmp_path, code['Verify Twilio signature'], {
            'Settings': settings, 'Twilio WhatsApp message in': {'headers': headers, 'body': params, 'query': {}, 'webhookUrl': webhook_url}})

    on = {'twilio_auth_token': token, 'webhook_public_url': ''}
    assert verify(on, {'x-twilio-signature': sig, 'host': 'n8n.example.com', 'x-forwarded-proto': 'https'})['valid'] is True  # URL from proxy headers
    assert verify(on, {'x-twilio-signature': sig}, webhook_url=url)['valid'] is True                                           # n8n's own webhookUrl
    assert verify({**on, 'webhook_public_url': url}, {'x-twilio-signature': sig})['valid'] is True                             # Settings override
    assert verify(on, {'x-twilio-signature': 'forged', 'host': 'n8n.example.com'})['valid'] is False
    assert verify(on, {'host': 'n8n.example.com'})['valid'] is False                                                           # unsigned
    off = verify({'twilio_auth_token': '', 'webhook_public_url': ''}, {})
    assert off['valid'] is True and off['checked'] is False

    def lane(body, media=None):
        msg = {'From': 'whatsapp:+919800012345', 'Body': body, 'To': 'whatsapp:+14155238886', 'NumMedia': '1' if media else '0'}
        if media:
            msg.update(MediaUrl0='https://api.twilio.com/m/ME1', MediaContentType0=media)
        return _run_n8n_code(tmp_path, code['Classify message'], {'Settings': {'relay_token': 'r', 'twilio_auth_token': ''},
                                                                   'Twilio WhatsApp message in': {'body': msg}})
    first = lane('Atta 5kg MRP 280 sell 250 cost 230')
    assert first['lane'] == 'text' and first['to'] == '+919800012345' and re.fullmatch(r'[0-9a-f]{12}', first['senderRef'])
    assert lane('Diwali plan budget 40000 Delhi')['lane'] == 'plan' and lane('STOP')['lane'] == 'stop'
    assert lane('', media='image/jpeg')['lane'] == 'photo' and lane('status')['lane'] == 'text'


def _studio_run(client, flow, body, phone=PHONE, media=''):
    """Runs a Studio flow definition the way Studio does, for the widgets and the Liquid this flow uses."""
    states = {s['name']: s for s in flow['states']}
    ctx = {'trigger': {'message': {'From': phone, 'Body': body, 'NumMedia': '1' if media else '0', 'MediaUrl0': media}},
           'flow': {'variables': {}, 'channel': {'address': 'whatsapp:+14155238886'}}, 'contact': {'channel': {'address': phone}}, 'widgets': {}}

    def look(path):
        cur = ctx
        for part in path.strip().split('.'):
            cur = cur.get(part) if isinstance(cur, dict) else None
        return '' if cur is None else cur

    def render(t):
        m = re.fullmatch(r'\{% if ([\w.]+) %\}(.*)\{% else %\}(.*)\{% endif %\}', t, re.S)
        if m:
            return render(m.group(2) if look(m.group(1)) != '' else m.group(3))

        def one(mm):
            expr = mm.group(1)
            if '| plus:' in expr:
                var, n = expr.split('| plus:')
                return str(int(look(var)) + int(n))
            return str(look(expr))
        return re.sub(r'\{\{(.*?)\}\}', one, t)

    sent, runs, name = [], {}, flow['initial_state']
    for _ in range(1000):  # Studio's step limit
        st = states[name]
        runs[name] = runs.get(name, 0) + 1
        assert runs[name] < 10, f'{name} ran 10 times: Studio would end the execution'
        kind, p, nxt, event = st['type'], st['properties'], None, None
        if kind == 'trigger':
            event = 'incomingMessage'
        elif kind == 'make-http-request':
            u = urlsplit(render(p['url']))
            path = u.path + ('?' + u.query if u.query else '')
            params = {x['key']: render(x['value']) for x in p.get('parameters', [])}
            r = client.post(path, data=params, auth=(u.username, u.password)) if p['method'] == 'POST' else client.get(path, auth=(u.username, u.password))
            ok = 200 <= r.status_code < 300
            ctx['widgets'][name] = {'status_code': r.status_code, 'parsed': r.json() if ok else {}}
            event = 'success' if ok else 'failed'
        elif kind == 'split-based-on':
            value, event = render(p['input']), 'noMatch'
            for tr in st['transitions']:
                c = (tr.get('conditions') or [None])[0]
                if tr['event'] == 'match' and ((c['type'] == 'equal_to' and value == c['value'])
                                              or (c['type'] == 'less_than' and value != '' and float(value) < float(c['value']))):
                    event, nxt = None, tr.get('next')
                    break
        elif kind == 'set-variables':
            ctx['flow']['variables'].update({v['key']: render(v['value']) for v in p['variables']})
            event = 'next'
        elif kind == 'send-message':
            assert render(p['from']) == 'whatsapp:+14155238886' and render(p['to']) == phone
            sent.append(render(p['body']))
            event = 'sent'
        if event:
            nxt = next((tr.get('next') for tr in st['transitions'] if tr['event'] == event), None)
        if not nxt:
            return sent, runs
        name = nxt
    raise AssertionError('Studio step limit')


def _studio(wait='7'):
    raw = STUDIO.read_text(encoding='utf-8')
    assert 'REPLACE_WITH_SHUBHLABH_RELAY_TOKEN' in raw and 'REPLACE_WITH_SHUBHLABH_HOST' in raw  # placeholders, no secrets
    raw = raw.replace('REPLACE_WITH_SHUBHLABH_RELAY_TOKEN', RELAY).replace('REPLACE_WITH_SHUBHLABH_HOST', 'testserver').replace('wait=7', 'wait=' + wait)
    flow = json.loads(raw)
    names = {s['name'] for s in flow['states']}
    assert flow['initial_state'] in names and len(names) == len(flow['states'])
    assert all(t.get('next') in (None, *names) for s in flow['states'] for t in s['transitions'])
    return flow


def test_studio_flow_replies_plans_and_reads_slow_photos(client, monkeypatch):
    flow = _studio()
    sent, _ = _studio_run(client, flow, 'Atta 5kg MRP 280 sell 250 cost 230')
    assert len(sent) == 1 and 'Profit ₹20 per unit' in sent[0]
    sent, runs = _studio_run(client, flow, 'Diwali plan budget 40000 Delhi', phone='whatsapp:+919876500005')
    assert len(sent) == 2 and 'Planning your Diwali campaign' in sent[0] and 'Your Diwali plan is ready' in sent[1], sent
    assert max(runs.values()) <= 8
    real = W.handle

    def slow(*a, **k):
        time.sleep(0.6)
        return real(*a, **k)
    monkeypatch.setattr(W, 'handle', slow)
    sent, runs = _studio_run(client, _studio(wait='0.2'), 'Holi', phone='whatsapp:+919876500006')
    assert len(sent) == 2 and 'reading the prices' in sent[0] and 'Holi' in sent[1] and runs['poll_job'] <= 8


def test_studio_flow_gives_up_politely_within_studio_limits(client, monkeypatch):
    monkeypatch.setattr(P.campaign, 'start', _fake_campaign('running'))  # a plan that never finishes
    sent, runs = _studio_run(client, _studio(wait='0'), 'Diwali plan', phone='whatsapp:+919876500007')
    assert 'Planning your Diwali campaign' in sent[0] and 'taking longer than usual' in sent[-1]
    assert all(n <= 8 for n in runs.values()) and runs['poll_plan_3'] == 8
