"""Festival templates for the One-Click AI Campaign Designer.

Each template pre-fills the brief (cities, goal, budget, depth, mechanisms, days) and declares
which categories lift in which city. Lifts are labelled planning assumptions; lunar-calendar
dates vary by region and panchang, so every date is editable in the UI and marked 'verify'.
"""
from datetime import date

ALL = ['Bengaluru', 'Mumbai', 'Delhi']
F = []
def fest(id, name, start, end, tagline, goal, budget_inr, depth, mechs, lifts, palette, channels, note='', verify=True, audience='Family baskets'):
    F.append({'id': id, 'name': name, 'start': start, 'end': end, 'tagline': tagline, 'objective': goal,
              'budget_paise': budget_inr * 100, 'max_discount_bps': depth, 'mechanisms': mechs, 'lifts': lifts,
              'palette': palette, 'channels': channels, 'note': note, 'verify_date': verify, 'audience': audience})

fest('navratri', 'Navratri', '2026-10-11', '2026-10-19', 'Nine nights of garba, fasting and family feasts', 'profit', 30000, 2000,
     ['markdown', 'bundle', 'coupon'], {'Delhi': (['Dairy & fresh', 'Snacks', 'Beverages'], 1.22), 'Mumbai': (['Beverages', 'Snacks'], 1.15), 'Bengaluru': (['Staples', 'Dairy & fresh'], 1.08)},
     {'primary': '#C2185B', 'accent': '#FFB300', 'ink': '#3B0A24'}, ['WhatsApp', 'Shelf', 'App banner'], 'Vrat-friendly staples and dairy lead in the north', verify=False)
fest('dussehra', 'Dussehra', '2026-10-20', '2026-10-21', 'Victory day: Mysuru Dasara, Ayudha Puja and gifting', 'profit', 25000, 2000,
     ['markdown', 'bundle'], {'Bengaluru': (['Staples', 'Home essentials', 'Snacks'], 1.20), 'Delhi': (['Snacks', 'Beverages'], 1.12), 'Mumbai': (['Snacks'], 1.10)},
     {'primary': '#D84315', 'accent': '#FFC107', 'ink': '#3E1407'}, ['Shelf', 'WhatsApp'], verify=False)
fest('karwa_chauth', 'Karwa Chauth', '2026-10-29', '2026-10-29', 'Sargi baskets and evening feasts', 'profit', 15000, 1500,
     ['bundle', 'markdown'], {'Delhi': (['Dairy & fresh', 'Snacks', 'Beverages'], 1.18)}, {'primary': '#B71C1C', 'accent': '#F9A825', 'ink': '#3A0B0B'},
     ['WhatsApp', 'App banner'], 'Mostly north India', audience='Family baskets')
fest('diwali', 'Dhanteras & Diwali', '2026-11-06', '2026-11-08', 'Festival of lights: stocking up, sweets, gifting and cleaning', 'profit', 60000, 2000,
     ['markdown', 'coupon', 'bundle'], {'Delhi': (['Snacks', 'Beverages', 'Home essentials'], 1.30), 'Mumbai': (['Snacks', 'Beverages', 'Home essentials'], 1.25), 'Bengaluru': (['Snacks', 'Home essentials'], 1.18)},
     {'primary': '#6A1B9A', 'accent': '#FFC400', 'ink': '#1E0833'}, ['WhatsApp', 'Shelf', 'App banner'], 'Biggest grocery week of the year', verify=False)
fest('bhai_dooj', 'Bhai Dooj', '2026-11-10', '2026-11-10', 'Sibling gifting and sweets', 'profit', 12000, 1500,
     ['bundle', 'markdown'], {'Delhi': (['Snacks', 'Beverages'], 1.12), 'Mumbai': (['Snacks'], 1.08)}, {'primary': '#AD1457', 'accent': '#FFD54F', 'ink': '#36081C'}, ['WhatsApp'])
fest('chhath', 'Chhath Puja', '2026-11-14', '2026-11-15', 'Thekua, fruit and fasting essentials', 'clearance', 12000, 1500,
     ['markdown', 'bundle'], {'Delhi': (['Staples', 'Dairy & fresh'], 1.20), 'Mumbai': (['Staples'], 1.05)}, {'primary': '#EF6C00', 'accent': '#FFEB3B', 'ink': '#3D1B00'},
     ['WhatsApp', 'Shelf'], 'Strong in Bihar/UP communities; Delhi and Mumbai diaspora')
fest('black_friday', 'Black Friday', '2026-11-27', '2026-11-29', 'Deal weekend for app-first shoppers', 'profit', 40000, 2000,
     ['coupon', 'markdown'], {c: (['Home essentials', 'Beverages', 'Breakfast'], 1.15) for c in ALL}, {'primary': '#111111', 'accent': '#00E676', 'ink': '#000000'},
     ['App banner', 'WhatsApp'], 'Quick-commerce and app traffic peak', verify=False, audience='Convenience shoppers')
fest('christmas', 'Christmas', '2026-12-24', '2026-12-25', 'Cakes, cocoa and family baking', 'profit', 25000, 1500,
     ['bundle', 'markdown'], {'Mumbai': (['Breakfast', 'Beverages', 'Dairy & fresh'], 1.18), 'Bengaluru': (['Breakfast', 'Beverages', 'Dairy & fresh'], 1.20), 'Delhi': (['Beverages', 'Breakfast'], 1.10)},
     {'primary': '#C62828', 'accent': '#2E7D32', 'ink': '#2B0707'}, ['Shelf', 'WhatsApp'], verify=False)
fest('new_year', 'New Year', '2026-12-31', '2027-01-01', 'Party snacks, drinks and resolutions', 'profit', 30000, 1500,
     ['bundle', 'markdown', 'coupon'], {c: (['Snacks', 'Beverages'], 1.25) for c in ALL}, {'primary': '#0D47A1', 'accent': '#FFD600', 'ink': '#06132B'},
     ['App banner', 'WhatsApp'], verify=False, audience='Convenience shoppers')
fest('sankranti', 'Makar Sankranti & Pongal', '2027-01-14', '2027-01-15', 'Harvest festival: rice, jaggery, sesame and sugarcane', 'profit', 20000, 1500,
     ['markdown', 'bundle'], {'Bengaluru': (['Staples', 'Dairy & fresh'], 1.22), 'Mumbai': (['Staples'], 1.10), 'Delhi': (['Staples'], 1.08)},
     {'primary': '#F57F17', 'accent': '#43A047', 'ink': '#3A2200'}, ['Shelf', 'WhatsApp'], 'Pongal in the south, Sankranti/Uttarayan in the west', verify=False)
fest('republic_day', 'Republic Day sale', '2027-01-24', '2027-01-26', 'Long-weekend pantry restock', 'profit', 30000, 2000,
     ['markdown', 'coupon'], {c: (['Staples', 'Home essentials'], 1.12) for c in ALL}, {'primary': '#FF6F00', 'accent': '#1B5E20', 'ink': '#0A2A5E'},
     ['App banner', 'WhatsApp'], verify=False, audience='Value seekers')
fest('holi', 'Holi', '2027-03-21', '2027-03-22', 'Colours, gujiya, thandai and get-togethers', 'profit', 25000, 2000,
     ['bundle', 'markdown'], {'Delhi': (['Snacks', 'Beverages', 'Dairy & fresh'], 1.25), 'Mumbai': (['Snacks', 'Beverages'], 1.15), 'Bengaluru': (['Snacks'], 1.05)},
     {'primary': '#E91E63', 'accent': '#00BCD4', 'ink': '#2D0A1C'}, ['WhatsApp', 'App banner'])

def get(id):
    f = next((x for x in F if x['id'] == id), None)
    if not f:
        raise KeyError(id)
    return f

def upcoming(today=None):
    today = today or date.today()
    out = []
    for f in F:
        days = (date.fromisoformat(f['start']) - today).days
        out.append({**{k: v for k, v in f.items() if k != 'lifts'}, 'lifts': {c: {'categories': v[0], 'factor': v[1]} for c, v in f['lifts'].items()},
                    'days_away': days, 'status': 'live' if days <= 0 <= (date.fromisoformat(f['end']) - today).days else ('soon' if days <= 30 else 'later')})
    return sorted(out, key=lambda x: (x['days_away'] < -3, x['start']))

def calendar_for(f, cities, horizon, lead_days=1):
    """Festival demand factors laid onto the planning days 0..horizon-1 (day `lead_days` = festival start)."""
    span = (date.fromisoformat(f['end']) - date.fromisoformat(f['start'])).days + 1
    out = []
    for day in range(horizon):
        rel = day - lead_days
        factor_day = 0 <= rel < span or rel == -1  # the eve also lifts shopping
        if not factor_day:
            continue
        for city, (cats, factor) in f['lifts'].items():
            if city in cities:
                out.append({'name': f['name'], 'day': day, 'city': city, 'categories': cats,
                            'factor': factor if rel >= 0 else round(1 + (factor - 1) * 0.6, 3), 'status': 'assumed',
                            'source': 'Festival template; demand factor is a planning assumption'})
    return out
