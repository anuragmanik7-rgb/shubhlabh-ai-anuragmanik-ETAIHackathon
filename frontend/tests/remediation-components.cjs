/* Local regression checks: actual TypeScript modules and JSX handlers, no browser,
 * server, network, package installation or model calls. Run from frontend:
 *   node tests/remediation-components.cjs
 * PROMOPILOT_TEST_SRC may point to a preserved frontend/src for baseline checks.
 * Hooks are a small deterministic harness; this does not replace browser QA.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const {test} = require('node:test');
const ts = require('typescript');
const jsx = require('react/jsx-runtime');

const sourceRoot = path.resolve(process.env.PROMOPILOT_TEST_SRC || path.join(__dirname, '../src'));
const clone = value => JSON.parse(JSON.stringify(value));
const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);

function textOf(tree) {
  if (tree == null || typeof tree === 'boolean') return '';
  if (typeof tree !== 'object') return String(tree);
  return Array.isArray(tree) ? tree.map(textOf).join('') : textOf(tree.props?.children);
}
function nodes(tree) {
  if (!tree || typeof tree !== 'object') return [];
  return Array.isArray(tree) ? tree.flatMap(nodes) : [tree, ...nodes(tree.props?.children)];
}
function button(tree, label) {
  const found = nodes(tree).find(node => node.type === 'button' && textOf(node).trim() === label);
  assert.ok(found, `Expected button: ${label}`);
  return found;
}
function bindingNames(filename, componentName) {
  const parsed = ts.createSourceFile(filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true);
  const result = [];
  function visit(node, inside = false) {
    const selected = ts.isFunctionDeclaration(node) && node.name?.text === componentName;
    if (ts.isVariableDeclaration(node) && inside && ts.isArrayBindingPattern(node.name)
        && node.initializer && ts.isCallExpression(node.initializer)
        && node.initializer.expression.getText(parsed) === 'useState') {
      result.push(node.name.elements[0].name.text);
    }
    ts.forEachChild(node, child => visit(child, inside || selected));
  }
  visit(parsed);
  return result;
}
function harness(apiOverrides = {}) {
  const cache = new Map();
  let current = null;
  const react = {
    useState(initial) {
      assert.ok(current, 'Component must be mounted before executing hooks');
      const host = current;
      const index = host.stateIndex++;
      const name = host.names[index] || `state_${index}`;
      if (!own(host.state, name)) host.state[name] = typeof initial === 'function' ? initial() : initial;
      return [host.state[name], value => {
        host.state[name] = typeof value === 'function' ? value(host.state[name]) : value;
      }];
    },
    useRef(initial) {
      const index = current.refIndex++;
      return current.refs[index] || (current.refs[index] = {current: initial});
    },
    useEffect() {},
    useMemo(fn) { return fn(); },
    useCallback(fn) { return fn; },
  };
  const icons = new Proxy({}, {get: (_target, key) => key === '__esModule' ? true : props => jsx.jsx('mock-icon', {...props, name: key})});
  const mockedApi = {
    money: value => `INR ${(value || 0) / 100}`,
    number: value => String(value), timestamp: value => value,
    setCsrf() {}, ...apiOverrides,
  };
  function load(file, actualApi = false) {
    const filename = path.resolve(sourceRoot, file);
    if (cache.has(filename)) return cache.get(filename).exports;
    const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX},
      fileName: filename,
    }).outputText;
    const loaded = new Module(filename, module);
    loaded.filename = filename;
    cache.set(filename, loaded);
    loaded.require = id => {
      if (id === 'react') return react;
      if (id === 'react/jsx-runtime') return jsx;
      if (id === 'lucide-react' || id === 'recharts') return icons;
      if (id === './api' && !actualApi) return mockedApi;
      if (id.startsWith('.')) {
        const target = path.resolve(path.dirname(filename), id);
        const resolved = [target, `${target}.ts`, `${target}.tsx`].find(item => fs.existsSync(item));
        assert.ok(resolved, `Missing source module ${id}`);
        return load(path.relative(sourceRoot, resolved), actualApi);
      }
      return require(id);
    };
    loaded._compile(code, filename);
    return loaded.exports;
  }
  function mount(file, componentName, props = {}, overrides = {}) {
    const exported = load(file);
    const component = componentName === 'App' ? exported.default : exported[componentName] || exported.default;
    assert.equal(typeof component, 'function', `Expected component ${componentName}`);
    const host = {
      state: {...overrides}, refs: [], names: bindingNames(path.join(sourceRoot, file), componentName),
      props, stateIndex: 0, refIndex: 0,
      render() {
        const previous = current;
        current = host; host.stateIndex = 0; host.refIndex = 0;
        try { host.tree = component(host.props); return host.tree; }
        finally { current = previous; }
      },
    };
    host.render();
    return host;
  }
  const actualApi = load('api.ts', true);
  if (actualApi.ApiError) mockedApi.ApiError = actualApi.ApiError;
  return {load, mount, mockedApi};
}

const envelope = {
  max_budget_paise: 100000, max_discount_bps: 700, min_margin_bps: 2300,
  cities: ['Delhi'], mechanisms: ['coupon'], allow_auto_replan: false,
  permitted_skus: ['SKU001'], date_from: '2026-10-01', date_to: '2026-10-02',
  max_changed_offer_fraction: 0.1,
};
const policy = {max_discount_bps: 2000, min_margin_bps: 1500};
const overview = {
  policy, envelope, events: [], orders: [], budget_paise: 3000000,
  reserved_paise: 0, spent_paise: 0, at_risk_units: 0,
};
const samplePlan = {
  id: 'narrow-plan', revision: 1, status: 'awaiting_approval', mode: 'offline',
  brief: {title: 'Delhi-only INR 1,000', cities: ['Delhi'], budget_paise: 100000, horizon: 3},
  offers: [], validation: {liability_paise: 0}, simulation: {incremental_contribution_paise: 0},
};
const catalog = {products: [], inventory: []};
function app(apiOverrides = {}, overrides = {}) {
  const h = harness({
    api: async route => route === '/overview' ? clone(overview)
      : route === '/catalog' ? clone(catalog) : route === '/plans' ? [clone(samplePlan)]
      : route === '/evaluations' ? {} : [],
    ...apiOverrides,
  });
  return {...h, host: h.mount('App.tsx', 'App', {}, {
    view: 'overview', session: {role: 'demo'}, overview: clone(overview),
    catalog: clone(catalog), plans: [clone(samplePlan)], plan: clone(samplePlan),
    loading: false, ...overrides,
  })};
}

test('all saved plans, including an older active revision, remain selectable', () => {
  const plans = Array.from({length: 6}, (_unused, index) => ({
    ...clone(samplePlan), id: `plan-${index}`, status: index === 5 ? 'active' : 'awaiting_approval',
    brief: {...samplePlan.brief, title: `Saved plan ${index}`},
  }));
  const {host} = app({}, {plans, plan: plans[0]});
  const choices = nodes(host.tree).filter(node => node.type === 'button' && textOf(node).includes('Saved plan 5'));
  const option = nodes(host.tree).find(node => node.type === 'option' && node.props.value === plans[5].id);
  assert.ok(choices.length || option, 'Older active plan must be reachable through a visible plan control');
  if (choices.length) choices[0].props.onClick();
  else {
    const select = nodes(host.tree).find(node => node.type === 'select' && nodes(node).includes(option));
    select.props.onChange({target: {value: plans[5].id}});
  }
  assert.equal(host.state.plan.id, plans[5].id);
});

test('catalog totals include every matching batch and exclude other SKU/city stock', () => {
  const {host} = app({}, {view: 'sandbox', catalog: {
    products: [{sku: 'SKU001', name: 'Synthetic Rice', category: 'Staples', family: 'Rice', pack_quantity: 1, pack_unit: 'kg', price_paise: 10000}],
    inventory: [
      {sku: 'SKU001', city: 'Bengaluru', sellable: 5, reserved: 2, expiry: '2026-10-03'},
      {sku: 'SKU001', city: 'Bengaluru', sellable: 8, reserved: 3, expiry: '2026-10-07'},
      {sku: 'SKU001', city: 'Delhi', sellable: 100, reserved: 50, expiry: '2026-10-02'},
      {sku: 'SKU002', city: 'Bengaluru', sellable: 200, reserved: 70, expiry: '2026-10-01'},
    ],
  }});
  const card = nodes(host.tree).find(node => node.props?.className === 'catalog-card');
  assert.match(textOf(card), /13 sellable/);
  assert.match(textOf(card), /Reserved 5/);
});

test('validation error preserves actionable field details and correlation identity', async () => {
  const actual = harness().load('api.ts', true);
  const response = {code: 'VALIDATION_ERROR', message: 'Check the submitted fields',
    field_errors: {'body.budget_paise': 'Input should be greater than or equal to 0'},
    correlation_id: 'synthetic-correlation-123'};
  const previous = global.fetch;
  global.fetch = async () => ({ok: false, status: 422, headers: new Headers(), json: async () => response});
  try {
    await assert.rejects(actual.post('/plans', {budget_paise: -1}), error => {
      assert.match(error.message, /greater than or equal to 0/);
      assert.equal(error.status, 422);
      assert.deepEqual(error.fieldErrors || error.field_errors, response.field_errors);
      assert.equal(error.correlationId || error.correlation_id, response.correlation_id);
      return true;
    });
  } finally { global.fetch = previous; }
});

test('saving a checkbox-only envelope change preserves every existing scope limit', async () => {
  const posted = [];
  const h = app({post: async (route, payload) => {posted.push({route, payload: clone(payload)}); return payload;}}, {view: 'approvals'});
  const child = nodes(h.host.tree).find(node => typeof node.type === 'function' && node.type.name === 'AuthorityEditor');
  const host = child ? h.mount('AuthorityEditor.tsx', 'AuthorityEditor', child.props) : h.host;
  const checkbox = nodes(host.tree).find(node => node.type === 'input' && node.props.type === 'checkbox'
    && (node.props.checked === false));
  assert.ok(checkbox, 'Automatic-activation toggle must be present');
  checkbox.props.onChange({target: {checked: true}});
  host.render();
  const form = nodes(host.tree).find(node => node.type === 'form');
  if (form) {
    await form.props.onSubmit({preventDefault() {}});
    assert.equal(posted.length, 0, 'Enabling automatic activation requires deliberate review');
    host.render();
    const review = nodes(host.tree).find(node => node.type === 'input' && node.props.type === 'checkbox' && node.props.required);
    assert.ok(review, 'Expanded authority review must be explicit');
    review.props.onChange({target: {checked: true}});
    host.render();
    await nodes(host.tree).find(node => node.type === 'form').props.onSubmit({preventDefault() {}});
  } else await button(host.tree, 'Save authority envelope').props.onClick();
  const saved = posted.find(request => request.route === '/envelope');
  assert.ok(saved, 'Expected envelope save through the real handler');
  assert.deepEqual(saved.payload, {...envelope, allow_auto_replan: true});
});

test('authority review resets after any subsequent scope edit', async () => {
  const posted = [];
  const h = harness();
  const host = h.mount('AuthorityEditor.tsx', 'AuthorityEditor', {
    envelope: clone(envelope), policy, plan: samplePlan, products: [], busy: false,
    onSave: async value => {posted.push(clone(value));},
  });
  let budget = nodes(host.tree).find(node => node.props?.id === 'authority-budget');
  budget.props.onChange({target: {value: '1100'}});
  host.render();
  nodes(host.tree).find(node => node.type === 'input' && node.props.type === 'checkbox' && node.props.required)
    .props.onChange({target: {checked: true}});
  host.render();
  budget = nodes(host.tree).find(node => node.props?.id === 'authority-budget');
  budget.props.onChange({target: {value: '1500'}});
  host.render();
  await nodes(host.tree).find(node => node.type === 'form').props.onSubmit({preventDefault() {}});
  assert.equal(posted.length, 0, 'An approval of INR 1,100 must not authorize a later INR 1,500 edit');
  host.render();
  assert.match(textOf(nodes(host.tree).find(node => node.props?.role === 'alert')), /Review/);
});

test('authority rejects empty SKU scope and reversed dates while retaining edits', async () => {
  const posted = [];
  const h = harness();
  const host = h.mount('AuthorityEditor.tsx', 'AuthorityEditor', {
    envelope: clone(envelope), policy, plan: samplePlan, products: [], busy: false,
    onSave: async value => {posted.push(clone(value));},
  });
  nodes(host.tree).find(node => node.props?.id === 'authority-skus').props.onChange({target: {value: ''}});
  host.render();
  await nodes(host.tree).find(node => node.type === 'form').props.onSubmit({preventDefault() {}});
  host.render();
  assert.equal(posted.length, 0);
  assert.match(textOf(nodes(host.tree).find(node => node.props?.role === 'alert')), /SKU/);
  assert.equal(nodes(host.tree).find(node => node.props?.id === 'authority-skus').props.value, '');
  nodes(host.tree).find(node => node.props?.id === 'authority-skus').props.onChange({target: {value: 'SKU001'}});
  host.render();
  nodes(host.tree).find(node => node.props?.id === 'authority-to').props.onChange({target: {value: '2026-09-30'}});
  host.render();
  await nodes(host.tree).find(node => node.type === 'form').props.onSubmit({preventDefault() {}});
  host.render();
  assert.equal(posted.length, 0);
  assert.match(textOf(nodes(host.tree).find(node => node.props?.role === 'alert')), /date window/);
});

test('a new authority envelope derives explicit limits from the selected plan', () => {
  const {authorityDraft, authorityPayload} = harness().load('AuthorityEditor.tsx');
  const plan = {...samplePlan, brief: {...samplePlan.brief, mechanisms: ['coupon'],
    max_discount_bps: 900, min_margin_bps: 2200, start_date: '2026-10-10'},
    offers: [{skus: ['SKU001', 'SKU002']}, {skus: ['SKU001']}]};
  const payload = authorityPayload(authorityDraft(null, policy, plan));
  assert.deepEqual(payload, {
    max_budget_paise: 100000, max_discount_bps: 900, min_margin_bps: 2200,
    cities: ['Delhi'], mechanisms: ['coupon'], allow_auto_replan: false,
    permitted_skus: ['SKU001', 'SKU002'], date_from: '2026-10-10', date_to: '2026-10-12',
    max_changed_offer_fraction: 0,
  });
});

test('each expansion of authority requires review; reductions do not', () => {
  const {authorityDraft, expandsAuthority} = harness().load('AuthorityEditor.tsx');
  const base = authorityDraft(envelope, policy, samplePlan);
  assert.equal(expandsAuthority(base, envelope), false);
  const changes = [
    {max_budget_paise: 100001}, {max_discount_bps: 701}, {min_margin_bps: 2299},
    {cities: ['Delhi', 'Mumbai']}, {mechanisms: ['coupon', 'bundle']},
    {permitted_skus_text: 'SKU001, SKU002'}, {date_from: '2026-09-30'},
    {date_to: '2026-10-03'}, {max_changed_offer_fraction: 0.11}, {allow_auto_replan: true},
  ];
  for (const change of changes) assert.equal(expandsAuthority({...base, ...change}, envelope), true, JSON.stringify(change));
  assert.equal(expandsAuthority({...base, max_budget_paise: 50000, max_discount_bps: 600,
    min_margin_bps: 2500, max_changed_offer_fraction: 0}, envelope), false);
});

test('mutation identity survives ambiguous retry and reload, then advances only after acknowledgement', () => {
  const {MutationIds} = harness().load('ui-state.ts');
  const data = new Map();
  const storage = {getItem: key => data.get(key) || null, setItem: (key, value) => data.set(key, value)};
  const body = {plan_id: 'plan-a', candidate_id: 'offer-a', quantity: 1};
  const registry = new MutationIds(storage);
  const first = registry.get('workspace-a:order', body, key => ({order_id: key}));
  assert.equal(first.body.order_id, first.key);
  assert.deepEqual(registry.get('workspace-a:order', {...body}, key => ({order_id: key})), first);
  const reloaded = new MutationIds(storage);
  assert.deepEqual(reloaded.get('workspace-a:order', body, key => ({order_id: key})), first);
  assert.notEqual(reloaded.get('workspace-b:order', body).key, first.key, 'Workspace identities must be isolated');
  assert.notEqual(reloaded.get('workspace-a:plan', body).key, first.key, 'Different operations must be isolated');
  assert.notEqual(reloaded.get('workspace-a:order', {...body, quantity: 2}).key, first.key, 'Different inputs must not reuse a key');
  reloaded.complete('workspace-a:order', body);
  assert.notEqual(new MutationIds(storage).get('workspace-a:order', body).key, first.key,
    'An acknowledged success permits a deliberate new redemption');
});

test('mutation retries remain stable when browser storage is unavailable or corrupt', () => {
  const {MutationIds} = harness().load('ui-state.ts');
  for (const storage of [
    {getItem() {throw new Error('storage disabled');}, setItem() {throw new Error('storage disabled');}},
    {getItem() {return '{broken';}, setItem() {}},
  ]) {
    const registry = new MutationIds(storage);
    const first = registry.get('workspace-a:plan', {budget_paise: 1000});
    assert.deepEqual(registry.get('workspace-a:plan', {budget_paise: 1000}), first);
  }
});

test('API preserves retry metadata and explains unreadable or interrupted responses', async () => {
  const actual = harness().load('api.ts', true);
  const previous = global.fetch;
  try {
    global.fetch = async () => ({ok: false, status: 429,
      headers: new Headers({'Retry-After': '42'}), json: async () => ({message: 'Wait before retrying'})});
    await assert.rejects(actual.api('/overview'), error => {
      assert.equal(error.status, 429); assert.equal(error.retryable, true); assert.equal(error.retryAfter, 42);
      assert.match(error.message, /Wait before retrying/); return true;
    });
    global.fetch = async () => ({ok: true, status: 200, headers: new Headers(), json: async () => {throw new Error('invalid JSON');}});
    await assert.rejects(actual.post('/sandbox/orders', {}), error => {
      assert.equal(error.code, 'INVALID_RESPONSE'); assert.equal(error.retryable, true);
      assert.match(error.message, /Retry the same action/); return true;
    });
    global.fetch = async () => {throw new TypeError('synthetic interrupted transport');};
    await assert.rejects(actual.post('/plans', {}), error => {
      assert.equal(error.status, 0); assert.equal(error.retryable, true);
      assert.match(error.message, /outcome is unknown/); return true;
    });
  } finally { global.fetch = previous; }
});

test('actual plan, event and redemption handlers preserve IDs after a lost response', async () => {
  const active = {...clone(samplePlan), status: 'active', offers: [{id: 'offer-a', name: 'Synthetic Rice',
    city: 'Delhi', mechanism: 'coupon', segment: 'Value seekers', price_paise: 1000}]};
  for (const scenario of [
    {view: 'planner', route: '/plans', label: 'Generate promotion plan', plan: null},
    {view: 'approvals', route: '/events', label: 'Apply event and replan', plan: samplePlan},
    {view: 'sandbox', route: '/sandbox/orders', label: 'Redeem once', plan: active},
  ]) {
    const posted = [];
    const h = app({
      post: async (route, body, headers) => {
        assert.equal(route, scenario.route);
        posted.push({route, body: clone(body), headers: clone(headers || {})});
        if (posted.length === 1) throw new TypeError('Synthetic lost response after server commitment');
        return scenario.route === '/plans' ? {id: 'run-a'} : {id: 'success'};
      },
      api: async route => route === '/overview' ? clone(overview)
        : route === '/catalog' ? clone(catalog) : route === '/plans' ? (scenario.plan ? [clone(scenario.plan)] : [])
        : route === '/evaluations' ? {} : route === '/runs/run-a' ? {id: 'run-a', state: 'validated', step: 7, mode: 'offline'} : [],
    }, {view: scenario.view, plan: clone(scenario.plan), session: {role: 'demo', tenant: `test-${scenario.route}`}});
    for (let i = 0; i < 3; i++) {
      await button(h.host.tree, scenario.label).props.onClick();
      h.host.render();
    }
    assert.equal(posted.length, 3, `${scenario.route}: all button handlers should execute`);
    assert.deepEqual(posted[1], posted[0], `${scenario.route}: ambiguous retry must preserve exact body and identity`);
    assert.notEqual(posted[2].headers['Idempotency-Key'], posted[0].headers['Idempotency-Key'],
      `${scenario.route}: acknowledged success allows a deliberate new action`);
    if (scenario.route === '/events') {
      assert.equal(posted[0].body.event_id, posted[0].headers['Idempotency-Key']);
      assert.ok(posted[0].body.observed_at, 'Event observation time must be frozen with its retry identity');
    }
    if (scenario.route === '/sandbox/orders') assert.equal(posted[0].body.order_id, posted[0].headers['Idempotency-Key']);
  }
});

test('a successful correction remains successful when the following refresh fails', async () => {
  let writes = 0;
  const h = app({
    post: async () => {writes++; return {id: 'confirmed-source'};},
    api: async () => {throw new Error('Synthetic refresh outage');},
  }, {view: 'evidence', evidenceEdit: {id: 'source-a', name: 'Synthetic policy',
    fields: {kind: 'policy', currency: 'INR', budget_paise: 100000}}});
  await button(h.host.tree, 'Confirm and apply new version').props.onClick();
  assert.equal(writes, 1);
  assert.equal(h.host.state.evidenceEdit, null, 'Confirmed data must not remain in a resubmittable correction dialog');
  assert.match(h.host.state.error, /action succeeded.*could not refresh/);
});
