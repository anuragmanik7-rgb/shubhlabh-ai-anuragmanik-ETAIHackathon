"""v2 API: agent runs, verified evidence, compiler, triage, explanations, guards and proof."""
import base64, json, os, re, time
from pathlib import Path
from typing import Literal
from fastapi import Depends, UploadFile, File, Form, Request
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from starlette.concurrency import run_in_threadpool
from .config import settings, ROOT
from .domain import AppError, Brief, now, uid, digest, CITIES
from .llm import LLM
from . import agent, compiler, extraction, relations, triage, explain, guards, whatsapp, whatsapp_plan
from .execution import approve

EVIDENCE_DIR = ROOT / 'evidence-set'
PROOF_DIR = ROOT / 'docs' / 'evidence'

class RunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    brief: Brief = Field(default_factory=Brief)
    policy: Literal['agent', 'rules', 'single_call'] = 'agent'
    chaos: list[Literal['solver_timeout']] = Field(default_factory=list)

class CompileRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=6000)
    brief: Brief = Field(default_factory=Brief)

class Answer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    answer: str = Field(min_length=1, max_length=1000)

class Approval(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)
    approver: str = Field(default='Category manager', max_length=80)
    senior_signoff: bool = False

class Question(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=2, max_length=1000)

class Confirm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    values: dict
    reviewer: str = Field(default='category manager', max_length=80)

class ApplyEvidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    city: str | None = None

class LiveEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_id: str | None = Field(default=None, max_length=80)
    kind: Literal['stock_drop', 'competitor_cut', 'sell_through_miss', 'budget_cut']
    sku: str | None = None
    city: str | None = None
    offer_id: str | None = None
    value: int = Field(ge=0, le=100000000)
    note: str = Field(default='', max_length=500)

class LintRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=2000)
    plan_id: str | None = None
    offer_id: str | None = None

class PriceCheck(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sku: str
    city: str
    price_inr: float = Field(gt=0, le=100000)
    claimed_pct_off: float | None = Field(default=None, ge=0, le=100)
    pricing_inputs: list[str] = Field(default_factory=lambda: ['sku', 'city', 'day'])

class Quarantine(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=20000)


def register(app, store, session, require_owner, ingest_in_worker):

    def ai_allowed(s):
        """Live model use: public judges allowed inside the daily cap, plus a per-workspace hourly limit."""
        if not settings.public_live:
            require_owner(s)
        hour = time.strftime('%Y%m%d%H'); key = f"{s['tenant']}:{hour}"
        store.put_new('_system', 'ai_runs', key, {'count': 0})
        def take(r, conn):
            if r['count'] >= 30:
                raise AppError('AI_RUN_LIMIT', 'This workspace used its 30 model-backed actions this hour; the rules policy still works', 429)
            r['count'] += 1
        store.mutate('_system', 'ai_runs', key, take)

    @app.get('/api/v2/status')
    def status(s=Depends(session)):
        usage = LLM(store).usage_today()
        return {'model_configured': LLM.available(), 'model': settings.openai_model, 'review_model': settings.openai_review_model,
                'daily_cap_usd': settings.daily_ai_limit, 'spent_today_usd': round(usage['cost_usd'], 4), 'calls_today': usage['calls'],
                'public_live': settings.public_live, 'role': s['role'], 'tenant': s['tenant'], 'cities': CITIES, 'today': now()[:10]}

    @app.get('/api/v2/state')
    def state_view(s=Depends(session)):
        st = store.get(s['tenant'], 'state', 'retailer')
        return {'name': st['name'], 'data_label': st['data_label'], 'policy': st['policy'], 'envelope': st.get('envelope'),
                'calendar': st['calendar'], 'segments': st['segments'], 'segment_definitions': guards.SEGMENT_DEFINITIONS,
                'products': [{k: p[k] for k in ('sku', 'name', 'category', 'pack_quantity', 'pack_unit', 'price_paise', 'mrp_paise', 'cost_paise')} for p in st['products']],
                'relationships': st['relationships'][:80], 'budget_left_paise': st['policy']['marketing_budget_paise'] - st['spent_paise'] - st['reserved_budget_paise'],
                'stale_competitors': len(agent.stale_competitors(st)), 'competitors': len(st['competitors'])}

    # ---------------------------------------------------------------- brief compiler
    @app.post('/api/v2/brief/compile')
    def compile_brief(body: CompileRequest, s=Depends(session)):
        st = store.get(s['tenant'], 'state', 'retailer')
        use_model = LLM.available()
        if use_model:
            try:
                ai_allowed(s)
            except AppError:
                use_model = False
        out = compiler.compile_text(store, body.brief.model_dump(), body.text, st, use_model)
        out['brief']['compiled_instruction'] = body.text.strip()  # accepted as the instruction: a run does not apply it twice
        return out

    # ---------------------------------------------------------------- agent runs
    @app.post('/api/v2/runs', status_code=202)
    def create_run(body: RunRequest, s=Depends(session)):
        policy = body.policy
        if policy != 'rules' and LLM.available():
            ai_allowed(s)
        brief = body.brief.model_dump()
        if policy == 'single_call':
            st = store.get(s['tenant'], 'state', 'retailer')
            if brief.get('instruction'):
                compiled = compiler.compile_text(store, brief, brief['instruction'], st, LLM.available())
                brief = compiled['brief']; brief['compiled_instruction'] = brief['instruction'].strip()
            policy = 'rules'
        return agent.public(agent.start_agent_run(store, s['tenant'], brief, policy, body.chaos))

    @app.get('/api/v2/runs')
    def list_runs(s=Depends(session)):
        return [{k: r.get(k) for k in ('id', 'status', 'policy', 'requested_policy', 'created_at', 'finished_at', 'plan_id', 'cost_usd', 'model_calls', 'trigger', 'parent_id')}
                for r in store.list(s['tenant'], 'agent_run')[:40]]

    @app.get('/api/v2/runs/{id}')
    def get_run(id: str, s=Depends(session)):
        return agent.public(store.get(s['tenant'], 'agent_run', id))

    @app.post('/api/v2/runs/{id}/answer')
    def answer(id: str, body: Answer, s=Depends(session)):
        return agent.public(agent.answer_run(store, s['tenant'], id, body.answer))

    # ---------------------------------------------------------------- plans
    @app.get('/api/v2/plans')
    def list_plans(s=Depends(session)):
        out = []
        for p in store.list(s['tenant'], 'plan')[:40]:
            out.append({k: p.get(k) for k in ('id', 'status', 'revision', 'created_at', 'mode', 'parent_id', 'agent_run_id', 'approval_tier', 'selected_portfolio')}
                       | {'offers': len(p['offers']), 'expected_paise': p['simulation']['incremental_contribution_paise']})
        return out

    @app.get('/api/v2/plans/{id}')
    def get_plan(id: str, s=Depends(session)):
        p = store.get(s['tenant'], 'plan', id)
        p.pop('relationships', None)
        return p

    @app.post('/api/v2/plans/{id}/approve')
    def approve_plan(id: str, body: Approval, s=Depends(session)):
        p = store.get(s['tenant'], 'plan', id)
        tier = (p.get('approval_tier') or {}).get('tier', 'manager')
        if tier == 'senior' and not body.senior_signoff:
            raise AppError('SENIOR_SIGNOFF', 'This plan needs senior sign-off: worst-case liability above ₹15,000 or a discount of 20% or more', 403)
        result = approve(store, s['tenant'], id, body.revision)
        def note(plan, conn):
            plan['approval'] = {'by': body.approver, 'reason': body.reason, 'senior_signoff': body.senior_signoff, 'tier': tier, 'at': now()}
            return plan
        return store.mutate(s['tenant'], 'plan', id, note)

    @app.post('/api/v2/plans/{id}/explain')
    def explain_route(id: str, s=Depends(session)):
        p = store.get(s['tenant'], 'plan', id)
        if p.get('explanations'):
            return p['explanations']
        use_model = LLM.available()
        if use_model:
            try:
                ai_allowed(s)
            except AppError:
                use_model = False
        st = store.get(s['tenant'], 'state', 'retailer')
        result = explain.explain_plan(store, p, st, use_model)
        def save(plan, conn):
            plan['explanations'] = result; return plan
        store.mutate(s['tenant'], 'plan', id, save)
        return result

    @app.post('/api/v2/plans/{id}/offers/{offer_id}/copy')
    def copy_route(id: str, offer_id: str, s=Depends(session)):
        p = store.get(s['tenant'], 'plan', id)
        offer = next((c for c in p['offers'] if c['id'] == offer_id), None)
        if not offer:
            raise AppError('NOT_FOUND', 'Offer not found', 404)
        if offer.get('copy'):
            return offer['copy']
        use_model = LLM.available()
        if use_model:
            try:
                ai_allowed(s)
            except AppError:
                use_model = False
        st = store.get(s['tenant'], 'state', 'retailer')
        result = explain.offer_copy(store, {**offer, 'brief': p['brief']}, st, use_model)
        def save(plan, conn):
            for c in plan['offers']:
                if c['id'] == offer_id:
                    c['copy'] = result
            return plan
        store.mutate(s['tenant'], 'plan', id, save)
        return result

    @app.post('/api/v2/plans/{id}/ask')
    def ask_route(id: str, body: Question, s=Depends(session)):
        use_model = LLM.available()
        if use_model:
            try:
                ai_allowed(s)
            except AppError:
                use_model = False
        return explain.ask(store, s['tenant'], id, body.question, use_model)

    @app.get('/api/v2/plans/{id}/feed.json')
    def offer_feed(id: str, s=Depends(session)):
        """Machine-readable feed of APPROVED offers for shopping agents and marketplaces (schema.org Offer shape)."""
        p = store.get(s['tenant'], 'plan', id)
        if p['status'] not in ('approved', 'active'):
            raise AppError('NOT_APPROVED', 'Only approved or active plans are published as a feed', 409)
        st = store.get(s['tenant'], 'state', 'retailer'); products = {x['sku']: x for x in st['products']}
        from datetime import date, timedelta
        start = date.fromisoformat(p['brief'].get('window_start') or p['brief']['start_date'])   # campaign plans run on the kit's dates
        items = []
        for o in p['offers']:
            prior = (o.get('certificate') or {}).get('prior_price', [{}])[0]
            items.append({'@type': 'Offer', 'identifier': o['id'], 'itemOffered': [{'@type': 'Product', 'sku': k, 'name': products[k]['name'],
                          'size': f"{products[k]['pack_quantity']} {products[k]['pack_unit']}"} for k in o['skus']],
                          'price': o['price_paise'] / 100, 'priceCurrency': 'INR', 'areaServed': o['city'],
                          'validFrom': (start + timedelta(days=o['start_day'])).isoformat(),
                          'validThrough': (start + timedelta(days=o['start_day'] + o['duration'] - 1)).isoformat(),
                          'eligibleCustomerType': o['segment'], 'eligibleQuantity': {'maxValue': o['max_redemptions']},
                          'priceSpecification': {'mrp': sum(products[k]['mrp_paise'] for k in o['skus']) / 100,
                                                 'lowestPriceLast30Days': prior.get('reference_low_paise', 0) / 100 or None},
                          'promotionMechanism': o['mechanism'], 'minimumBasketInr': o['minimum_basket_paise'] / 100 or None,
                          'certificate': {'passed': (o.get('certificate') or {}).get('passed'), 'samePriceForEveryone': True}})
        return {'@context': 'https://schema.org', 'seller': st['name'], 'plan': p['id'], 'revision': p['revision'],
                'approvedBy': (p.get('approval') or {}).get('by'), 'generatedAt': now(), 'offers': items}

    # ---------------------------------------------------------------- evidence
    def slim(r):
        return {k: v for k, v in r.items() if k != 'preview_base64'}

    @app.get('/api/v2/evidence')
    def evidence_list(s=Depends(session)):
        items = store.list(s['tenant'], 'evidence2')
        superseded = {r.get('parent_id') for r in items}
        return [slim(r) | {'has_preview': 'preview_base64' in r} for r in items if r['id'] not in superseded][:60]

    @app.get('/api/v2/evidence/samples')
    def samples(s=Depends(session)):
        labels = json.loads((EVIDENCE_DIR / 'labels.json').read_text(encoding='utf-8'))['items']
        return [{'file': l['file'], 'type': l['type'], 'difficulty': l.get('difficulty'), 'red_team': l.get('red_team')} for l in labels]

    @app.get('/api/v2/evidence/samples/{name}')
    def sample_file(name: str, s=Depends(session)):
        path = (EVIDENCE_DIR / 'synthetic' / name).resolve()
        if path.parent != (EVIDENCE_DIR / 'synthetic').resolve() or not path.is_file():
            raise AppError('NOT_FOUND', 'Sample not found', 404)
        media = 'application/pdf' if path.suffix == '.pdf' else 'image/jpeg'
        return Response(path.read_bytes(), media_type=media, headers={'Cache-Control': 'max-age=3600'})

    async def run_extraction(s, name, content):
        st = store.get(s['tenant'], 'state', 'retailer')
        use_model = LLM.available()
        if use_model:
            try:
                ai_allowed(s)
            except AppError:
                use_model = False
        return slim(await ingest_in_worker(extraction.extract_file, store, s['tenant'], name, content, use_model, st['products']))

    @app.post('/api/v2/evidence/samples/{name}/extract')
    async def extract_sample(name: str, s=Depends(session)):
        path = (EVIDENCE_DIR / 'synthetic' / name).resolve()
        if path.parent != (EVIDENCE_DIR / 'synthetic').resolve() or not path.is_file():
            raise AppError('NOT_FOUND', 'Sample not found', 404)
        return await run_extraction(s, path.name, path.read_bytes())

    @app.post('/api/v2/evidence/upload')
    async def upload(file: UploadFile = File(...), s=Depends(session)):
        content = await file.read(settings.upload_limit + 1)
        if len(content) > settings.upload_limit:
            raise AppError('UPLOAD_LIMIT', 'Upload exceeds 8 MB', 413)
        return await run_extraction(s, file.filename or 'evidence.jpg', content)

    @app.get('/api/v2/evidence/{id}')
    def evidence_item(id: str, s=Depends(session)):
        return slim(store.get(s['tenant'], 'evidence2', id))

    @app.get('/api/v2/evidence/{id}/preview')
    def preview(id: str, s=Depends(session)):
        r = store.get(s['tenant'], 'evidence2', id)
        if 'preview_base64' not in r:
            raise AppError('NOT_FOUND', 'No image preview for this evidence', 404)
        return Response(base64.b64decode(r['preview_base64']), media_type='image/jpeg')

    @app.post('/api/v2/evidence/{id}/confirm')
    def confirm(id: str, body: Confirm, s=Depends(session)):
        return slim(extraction.confirm(store, s['tenant'], id, body.values, body.reviewer))

    @app.post('/api/v2/evidence/{id}/apply')
    def apply(id: str, body: ApplyEvidence, s=Depends(session)):
        return extraction.apply_to_competitors(store, s['tenant'], id, body.city)

    # ---------------------------------------------------------------- relationships
    @app.post('/api/v2/relations/infer')
    def infer(s=Depends(session)):
        use_model = LLM.available()
        if use_model:
            try:
                ai_allowed(s)
            except AppError:
                use_model = False
        return relations.infer(store, s['tenant'], use_model)

    # ---------------------------------------------------------------- live events
    @app.post('/api/v2/events')
    def live_event(body: LiveEvent, s=Depends(session)):
        st = store.get(s['tenant'], 'state', 'retailer')
        if body.kind in ('stock_drop', 'competitor_cut') and (body.sku not in {p['sku'] for p in st['products']} or body.city not in CITIES):
            raise AppError('EVENT_INPUT', 'Choose a known SKU and city')
        use_model = LLM.available()
        if use_model:
            try:
                ai_allowed(s)
            except AppError:
                use_model = False
        return triage.handle(store, s['tenant'], body.model_dump(), use_model, 'agent' if use_model else 'rules')

    @app.get('/api/v2/events')
    def events(s=Depends(session)):
        return store.list(s['tenant'], 'triage')[:40]

    # ---------------------------------------------------------------- guards (red-team demos)
    @app.post('/api/v2/guards/lint')
    def lint(body: LintRequest, s=Depends(session)):
        offer = cert = None
        if body.plan_id and body.offer_id:
            p = store.get(s['tenant'], 'plan', body.plan_id)
            offer = next((c for c in p['offers'] if c['id'] == body.offer_id), None)
            cert = (offer or {}).get('certificate')
        v = guards.lint_copy(body.text, offer, cert, offer['max_redemptions'] if offer else None)
        return {'passed': not v, 'violations': v}

    @app.post('/api/v2/guards/price-check')
    def price_check(body: PriceCheck, s=Depends(session)):
        st = store.get(s['tenant'], 'state', 'retailer')
        p = next((p for p in st['products'] if p['sku'] == body.sku), None)
        if not p or body.city not in CITIES:
            raise AppError('INPUT', 'Choose a known SKU and city')
        price = int(round(body.price_inr * 100)); low = guards.prior_price_low(st, p['sku'], body.city)
        honest = max(0, (low - price) * 100 / low)
        checks = [{'id': 'mrp', 'label': 'Never above MRP', 'passed': guards.mrp_ok(p, price), 'detail': f"₹{price/100:g} vs MRP {guards.rupees(p['mrp_paise'])}"},
                  {'id': 'margin', 'label': 'Above margin floor', 'passed': (price - p['cost_paise'] - p['variable_cost_paise']) * 10000 // max(1, price) >= st['policy']['min_margin_bps'],
                   'detail': f"Margin {(price - p['cost_paise'] - p['variable_cost_paise']) * 100 / price:.1f}% vs floor {st['policy']['min_margin_bps']/100:.0f}%"},
                  {'id': 'prior_price', 'label': 'Claimed % off honest against the 30-day low', 'passed': body.claimed_pct_off is None or body.claimed_pct_off <= honest + 0.5,
                   'detail': f"30-day low {guards.rupees(low)}; honest claim {honest:.0f}%" + (f"; claimed {body.claimed_pct_off:g}%" if body.claimed_pct_off is not None else '')},
                  {'id': 'same_price', 'label': 'Same price for everyone', **(lambda r: {'passed': r['passed'], 'detail': 'Blocked inputs: ' + ', '.join(r['blocked']) if r['blocked'] else 'Only SKU, city and day'})(guards.same_price_inputs_ok(body.pricing_inputs))}]
        return {'passed': all(c['passed'] for c in checks), 'checks': checks, 'product': p['name']}

    @app.post('/api/v2/guards/quarantine')
    def quarantine(body: Quarantine, s=Depends(session)):
        q = guards.quarantine(body.text); red, found = guards.redact(q['text'])
        return {**q, 'text': red, 'pii_redacted': found}

    # ---------------------------------------------------------------- one-click campaign designer
    from . import festivals as fests, campaign as camp, hf_forecast
    hf_forecast.warm_up_in_background()

    @app.get('/api/v2/festivals')
    def festival_list(s=Depends(session)):
        return {'festivals': fests.upcoming(), 'forecaster': hf_forecast.status()}

    @app.post('/api/v2/campaigns', status_code=202)
    async def create_campaign(inputs: str = Form('{}'), files: list[UploadFile] = File(default=[]), s=Depends(session)):
        try:
            data = json.loads(inputs)
        except ValueError:
            raise AppError('INPUTS', 'inputs must be JSON')
        allowed = {'festival_id', 'budget_paise', 'cities', 'goal', 'start', 'end', 'notes', 'ai_banners'}
        data = {k: v for k, v in data.items() if k in allowed}
        try:
            fests.get(data.get('festival_id') or 'navratri')
        except KeyError:
            raise AppError('FESTIVAL', 'Unknown festival template')
        if data.get('goal') not in (None, 'profit', 'clearance', 'conservative'):
            raise AppError('GOAL', 'Goal must be profit, clearance or conservative')
        if len(files) > 8:
            raise AppError('FILES', 'Upload up to 8 documents per campaign')
        payload = []
        for f in files:
            content = await f.read(settings.upload_limit + 1)
            if len(content) > settings.upload_limit:
                raise AppError('UPLOAD_LIMIT', f'{f.filename} exceeds 8 MB', 413)
            payload.append((f.filename or 'document', content))
        if LLM.available():
            try:
                ai_allowed(s)
            except AppError:
                pass
        return camp.start(store, s['tenant'], data, payload)

    @app.get('/api/v2/campaigns')
    def campaigns(s=Depends(session)):
        return [{k: c.get(k) for k in ('id', 'created_at', 'status', 'festival', 'plan_id')} for c in store.list(s['tenant'], 'campaign')[:30]]

    @app.get('/api/v2/campaigns/{id}')
    def campaign_get(id: str, s=Depends(session)):
        c = store.get(s['tenant'], 'campaign', id)
        if c.get('kit', {}) and c['kit'].get('ai_backgrounds'):
            c['kit']['ai_backgrounds'] = [{k: v for k, v in b.items() if k != 'b64'} | {'has_image': 'b64' in b} for b in c['kit']['ai_backgrounds']]
        return c

    @app.post('/api/v2/campaigns/{id}/ai-banners')
    def campaign_ai_banners(id: str, s=Depends(session)):
        if not LLM.available():
            raise AppError('API_KEY_REQUIRED', 'AI artwork needs the model key; template banners are already included', 503)
        ai_allowed(s)
        out = camp.ai_banners(store, s['tenant'], id)
        return [{k: v for k, v in b.items() if k != 'b64'} | {'has_image': 'b64' in b} for b in out]

    @app.get('/api/v2/campaigns/{id}/ai-banners/{offer_id}')
    def campaign_ai_banner(id: str, offer_id: str, s=Depends(session)):
        c = store.get(s['tenant'], 'campaign', id)
        b = next((b for b in (c.get('kit') or {}).get('ai_backgrounds', []) if b['offer_id'] == offer_id and 'b64' in b), None)
        if not b:
            raise AppError('NOT_FOUND', 'No AI artwork for this offer', 404)
        return Response(base64.b64decode(b['b64']), media_type='image/png', headers={'Cache-Control': 'max-age=3600'})

    # ---------------------------------------------------------------- proof
    @app.get('/api/v2/proof')
    def proof(s=Depends(session)):
        out = {}
        if PROOF_DIR.exists():
            for f in sorted(PROOF_DIR.glob('*.json')):
                try:
                    data = json.loads(f.read_text(encoding='utf-8'))
                    if isinstance(data, dict):
                        data.pop('rows', None); data.pop('runs', None)
                        if isinstance(data.get('cases'), list):
                            data.pop('cases')   # per-case detail; an integer count stays (the Proof page shows it)
                    out[f.stem] = data
                except ValueError:
                    continue
        return out

    # ---------------------------------------------------------------- WhatsApp: Twilio webhook (direct, n8n or Studio) + in-app simulator
    @app.get('/api/v2/whatsapp/status')
    def whatsapp_status(s=Depends(session)):
        return {'configured': bool(os.getenv('TWILIO_AUTH_TOKEN') or os.getenv('WHATSAPP_RELAY_TOKEN')),
                'channel': 'twilio' if os.getenv('TWILIO_AUTH_TOKEN') else ('n8n relay' if os.getenv('WHATSAPP_RELAY_TOKEN') else None),
                'number': os.getenv('WHATSAPP_NUMBER', ''), 'join_code': os.getenv('WHATSAPP_JOIN_CODE', ''),
                'webhook_path': '/api/v2/whatsapp/inbound', 'model_reads_photos': LLM.available(),
                'automation': {'plan_on_whatsapp': bool(os.getenv('WHATSAPP_RELAY_TOKEN')), 'plan_path': '/api/v2/whatsapp/plan'}}

    def wa_headers(request):
        return {k.lower(): v for k, v in request.headers.items()}

    @app.post('/api/v2/whatsapp/inbound')
    async def whatsapp_inbound(request: Request, format: str = '', wait: float = 0):
        """Twilio's webhook. TwiML by default (the direct webhook). The automation (n8n, Studio) asks for JSON with
        ?format=json, or Accept: application/json plus the relay token, and sends the reply itself. ?wait=N (Studio, which
        allows 10 s per request) answers within N seconds or returns a job id to poll."""
        form = await request.form()
        params = {k: str(v) for k, v in form.items()}
        headers = wa_headers(request)
        relayed = whatsapp.verify(str(request.url), params, headers) == 'n8n relay'
        if relayed and not params.get('From'):  # an HTTP widget that sent the fields as query parameters
            params.update({k: v for k, v in request.query_params.items() if k not in ('format', 'wait')})
        as_json = format.lower() == 'json' or (relayed and 'application/json' in headers.get('accept', ''))
        if as_json and wait > 0:
            jid = await run_in_threadpool(whatsapp.start_job, store, params)
            return await run_in_threadpool(whatsapp.job_view, store, jid, wait)
        out = await run_in_threadpool(whatsapp.respond, store, params)  # never raises: the apology on failure
        if as_json:
            return {'status': 'done', 'reply': out['reply'][:whatsapp.MAX_REPLY], 'intent': out['intent'], 'method': out.get('method')}
        return Response(whatsapp.twiml(out['reply']), media_type='application/xml')

    @app.get('/api/v2/whatsapp/jobs/{id}')
    def whatsapp_job(id: str, request: Request, wait: float = 0):
        """Automation only: the reply to a message that took longer than ?wait (a photo read by the model)."""
        whatsapp.require_relay(wa_headers(request))
        if not re.fullmatch(r'wajob_[0-9a-f]{16}', id):
            raise AppError('NOT_FOUND', 'Reply not found', 404)
        return whatsapp.job_view(store, id, wait)

    @app.post('/api/v2/whatsapp/plan')
    async def whatsapp_plan_start(request: Request):
        """Automation only (relay token): {From, Body} as JSON or a form -> a one-click campaign for this sender, started
        in the background. Returns the campaign id, the ack to send now and the texts for a timeout or an apology."""
        whatsapp.require_relay(wa_headers(request))
        if 'application/json' in request.headers.get('content-type', ''):
            try:
                data = await request.json()
            except ValueError:
                raise AppError('WHATSAPP_INPUT', 'Send {From, Body} as JSON or as a form')
            data = data if isinstance(data, dict) else {}
        else:
            data = {k: str(v) for k, v in (await request.form()).items()}
        phone = str(data.get('From') or '').strip()[:64]
        if not phone:
            raise AppError('WHATSAPP_INPUT', 'From is required (the sender, e.g. whatsapp:+91...)')
        return await run_in_threadpool(whatsapp_plan.start, store, phone, str(data.get('Body') or '')[:1000])

    @app.get('/api/v2/whatsapp/plan/{id}')
    def whatsapp_plan_view(id: str, request: Request, wait: float = 0):
        """Automation only: plan progress; ?wait=N long-polls up to 9 s. When finished, `summary` is the WhatsApp text."""
        whatsapp.require_relay(wa_headers(request))
        return whatsapp_plan.view(store, id, wait)

    @app.get('/api/v2/whatsapp/brief/{id}')
    def whatsapp_brief(id: str, sig: str = ''):
        """The printable brief behind the signed link in the WhatsApp summary (no login; the signature is the key)."""
        return Response(whatsapp_plan.brief_html(store, id, sig), media_type='text/html; charset=utf-8')

    @app.post('/api/v2/whatsapp/simulate')
    async def whatsapp_simulate(text: str = Form('', max_length=1000), sample: str = Form(''), file: UploadFile | None = File(None), s=Depends(session)):
        media = None
        if sample:
            path = (EVIDENCE_DIR / 'synthetic' / sample).resolve()
            if path.parent != (EVIDENCE_DIR / 'synthetic').resolve() or not path.is_file() or path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.pdf'):
                raise AppError('NOT_FOUND', 'Unknown sample', 404)
            media = (path.name, path.read_bytes(), 'application/pdf' if path.suffix == '.pdf' else 'image/jpeg')
        elif file is not None:
            content = await file.read(settings.upload_limit + 1)
            if len(content) > settings.upload_limit:
                raise AppError('UPLOAD_LIMIT', 'Photo exceeds 8 MB', 413)
            media = (file.filename or 'photo.jpg', content, file.content_type or 'image/jpeg')
        use_model = LLM.available() and media is not None
        if use_model:
            try:
                ai_allowed(s)
            except AppError:
                use_model = False
        out = await run_in_threadpool(whatsapp.handle, store, 'sim:' + s['tenant'], text, media, use_model)
        return {'reply': out['reply'], 'intent': out['intent'], 'method': out.get('method'), 'twiml': whatsapp.twiml(out['reply'])}
