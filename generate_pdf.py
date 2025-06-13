from fpdf import FPDF
import xmlrpc.client
import re
import os
import unicodedata
from datetime import datetime

# CONFIGURATIE
url = os.environ.get("ODOO_URL")
db = os.environ.get("ODOO_DB")
username = os.environ.get("ODOO_USER")
password = os.environ.get("ODOO_PASS")
logo_path = os.path.join(os.path.dirname(__file__), "assets", "acco_logo.png")

def clean_unicode(text):
    if not isinstance(text, str):
        return ''
    replacements = {
        '\u2019': "'", '\u2018': "'",
        '\u201c': '"', '\u201d': '"',
        '\u2026': '...', '\xa0': ' '
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    text = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in text if not unicodedata.combining(c))

common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

company_ids = models.execute_kw(db, uid, password, 'res.company', 'search', [[]], {'limit': 1})
company = models.execute_kw(db, uid, password, 'res.company', 'read', [company_ids], {'fields': ['name']})
company_name = clean_unicode(company[0]['name'])

# Zoek boekingsregels op 580900 in bankboekingen
lines_5809 = models.execute_kw(
    db, uid, password,
    'account.move.line', 'search_read',
    [[('account_id.code', '=', '580900'), ('move_id.journal_id.type', '=', 'bank')]],
    {'fields': ['move_id'], 'limit': 10000}
)
move_ids = list(set(line['move_id'][0] for line in lines_5809))

records = []
for move_id in move_ids:
    move_data = models.execute_kw(
        db, uid, password,
        'account.move', 'read',
        [move_id],
        {'fields': ['currency_id']}
    )
    currency = move_data[0]['currency_id'][1] if move_data and move_data[0]['currency_id'] else ''

    move_lines = models.execute_kw(
        db, uid, password,
        'account.move.line', 'search_read',
        [[('move_id', '=', move_id)]],
        {'fields': ['date', 'name', 'ref', 'account_id', 'debit', 'credit', 'journal_id', 'partner_id']}
    )

    account_ids = list(set([l['account_id'][0] for l in move_lines]))
    accounts = models.execute_kw(db, uid, password, 'account.account', 'read', [account_ids], {'fields': ['id', 'code']})
    account_map = {a['id']: a['code'] for a in accounts}

    narration_result = models.execute_kw(
        db, uid, password,
        'account.bank.statement.line', 'search_read',
        [[('move_id', '=', move_id)]],
        {'fields': ['narration'], 'limit': 1}
    )
    raw_narration = narration_result[0]['narration'] if narration_result else ''
    narration = clean_unicode(re.sub('<[^<]+?>', '', raw_narration).strip()) if isinstance(raw_narration, str) else ''

    for l in move_lines:
        acc_id = l['account_id'][0]
        acc_code = account_map.get(acc_id, '')
        if acc_code.startswith('5') and acc_code != '580900':
            amount = l['debit'] - l['credit']
            journal_name = clean_unicode(l['journal_id'][1]) if l.get('journal_id') else ''
            partner_name = clean_unicode(l['partner_id'][1]) if l.get('partner_id') else ''
            records.append({
                'date': l['date'],
                'type': journal_name,
                'name': clean_unicode(l['name']) or '',
                'narration': narration,
                'amount': amount,
                'partner': partner_name,
                'currency': currency
            })

# Sorteer op datum + type
records.sort(key=lambda r: (r['date'], r['type']))

headers = ["Datum", "Type", "Omschrijving", "Ref.", "Bedrag", "Partner"]
alignments = ['C', 'C', 'L', 'L', 'C', 'L']
widths = [25, 60, 35, 90, 35, 40]

class PDF(FPDF):
    def header(self):
        if os.path.exists(logo_path):
            self.image(logo_path, x=10, y=10, w=40)
        self.set_xy(10, 25)
        self.set_font("Arial", "B", 10)
        self.cell(0, 5, company_name, ln=True)
        self.set_xy(10, 35)
        self.set_font("Arial", "B", 14)
        self.cell(0, 8, "Ontbrekende documenten", ln=True)
        self.ln(5)

    def table_header(self):
        self.set_font("Arial", "B", 10)
        for i, header in enumerate(headers):
            self.cell(widths[i], 8, header, border=0, align=alignments[i])
        self.ln()
        self.set_draw_color(255, 102, 0)
        self.set_line_width(1.0)
        self.line(10, self.get_y(), 285, self.get_y())
        self.ln(2)
        self.set_font("Arial", "", 9)

pdf = PDF(orientation='L')
pdf.set_auto_page_break(auto=False)
pdf.add_page()
pdf.table_header()
pdf.set_font("Arial", size=9)

line_height = 5

for r in records:
    formatted_date = datetime.strptime(r['date'], "%Y-%m-%d").strftime("%d/%m/%Y")
    amount_str = f"{r['amount']:.2f} {r['currency']}"
    cell_data = [
        (formatted_date, widths[0], alignments[0]),
        (r['type'], widths[1], alignments[1]),
        (r['name'], widths[2], alignments[2]),
        (r['narration'], widths[3], alignments[3]),
        (amount_str, widths[4], alignments[4]),
        (r['partner'], widths[5], alignments[5])
    ]

    line_counts = [len(pdf.multi_cell(w, line_height, txt, split_only=True)) for txt, w, _ in cell_data]
    max_lines = max(line_counts)
    row_height = max_lines * line_height

    if pdf.get_y() + row_height > 195:
        pdf.add_page()
        pdf.table_header()

    x = pdf.get_x()
    y = pdf.get_y()

    for txt, w, align in cell_data:
        pdf.set_xy(x, y)
        pdf.multi_cell(w, line_height, txt, border=0, align=align)
        x += w

    pdf.set_y(y + row_height)
    pdf.ln(3)

output_filename = f"acco_OntbrekendeDocumenten_{db}.pdf"
pdf.output(output_filename)
print(f"✅ PDF gegenereerd als '{output_filename}'")
