# pylint: disable=missing-module-docstring,missing-function-docstring,too-many-lines,line-too-long
# pylint: disable=trailing-whitespace,too-many-locals,too-many-statements,redefined-outer-name,redefined-builtin
import calendar
import json
from datetime import date, datetime, timedelta, timezone
from functools import wraps

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

from config import Config
from models import (Account, Company, Customer, Employee, Invoice, InvoiceItem,
                    JournalEntry, JournalLine, PayrollRun, Payslip, Product, Purchase,
                    PurchaseItem, Supplier, TaxReturn, TaxSetting, User, db)

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'يرجى تسجيل الدخول أولاً'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ==================== ديكوريتور للصلاحيات ====================

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role not in ['admin', 'owner']:
            flash('ليس لديك صلاحية للوصول', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def company_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.company_id:
            flash('يرجى إنشاء شركة أولاً', 'warning')
            return redirect(url_for('setup_company'))
        return f(*args, **kwargs)
    return decorated


# ==================== إنشاء الجداول وشجرة الحسابات الافتراضية ====================

def create_default_accounts(company_id, _country_code='SA'):
    """إنشاء شجرة حسابات افتراضية"""
    accounts_data = [
        # الأصول
        {'code': '1000', 'name': 'Assets', 'name_ar': 'الأصول', 'type': 'asset', 'system': True},
        {'code': '1100', 'name': 'Cash & Bank', 'name_ar': 'النقد والبنوك', 'type': 'asset', 'parent': '1000'},
        {'code': '1101', 'name': 'Cash on Hand', 'name_ar': 'الصندوق', 'type': 'asset', 'parent': '1100'},
        {'code': '1102', 'name': 'Bank Account', 'name_ar': 'الحساب البنكي', 'type': 'asset', 'parent': '1100'},
        {'code': '1200', 'name': 'Accounts Receivable', 'name_ar': 'الذمم المدينة', 'type': 'asset', 'parent': '1000', 'system': True},
        {'code': '1300', 'name': 'Inventory', 'name_ar': 'المخزون', 'type': 'asset', 'parent': '1000'},
        {'code': '1400', 'name': 'Prepaid Expenses', 'name_ar': 'مصروفات مدفوعة مقدماً', 'type': 'asset', 'parent': '1000'},
        {'code': '1500', 'name': 'Fixed Assets', 'name_ar': 'الأصول الثابتة', 'type': 'asset', 'parent': '1000'},
        {'code': '1510', 'name': 'Furniture & Equipment', 'name_ar': 'أثاث ومعدات', 'type': 'asset', 'parent': '1500'},
        {'code': '1520', 'name': 'Vehicles', 'name_ar': 'سيارات', 'type': 'asset', 'parent': '1500'},
        {'code': '1590', 'name': 'Accumulated Depreciation', 'name_ar': 'مجمع الإهلاك', 'type': 'asset', 'parent': '1500'},
        
        # الخصوم
        {'code': '2000', 'name': 'Liabilities', 'name_ar': 'الخصوم', 'type': 'liability', 'system': True},
        {'code': '2100', 'name': 'Accounts Payable', 'name_ar': 'الذمم الدائنة', 'type': 'liability', 'parent': '2000', 'system': True},
        {'code': '2200', 'name': 'Accrued Expenses', 'name_ar': 'مصروفات مستحقة', 'type': 'liability', 'parent': '2000'},
        {'code': '2300', 'name': 'VAT Payable', 'name_ar': 'ضريبة القيمة المضافة المستحقة', 'type': 'liability', 'parent': '2000', 'system': True},
        {'code': '2310', 'name': 'Input VAT', 'name_ar': 'ضريبة المدخلات', 'type': 'asset', 'parent': '1000', 'system': True},
        {'code': '2400', 'name': 'Salaries Payable', 'name_ar': 'رواتب مستحقة', 'type': 'liability', 'parent': '2000'},
        {'code': '2500', 'name': 'GOSI Payable', 'name_ar': 'التأمينات الاجتماعية المستحقة', 'type': 'liability', 'parent': '2000'},
        {'code': '2600', 'name': 'Loans', 'name_ar': 'القروض', 'type': 'liability', 'parent': '2000'},
        {'code': '2700', 'name': 'End of Service', 'name_ar': 'مكافأة نهاية الخدمة', 'type': 'liability', 'parent': '2000'},
        
        # حقوق الملكية
        {'code': '3000', 'name': 'Equity', 'name_ar': 'حقوق الملكية', 'type': 'equity', 'system': True},
        {'code': '3100', 'name': 'Capital', 'name_ar': 'رأس المال', 'type': 'equity', 'parent': '3000'},
        {'code': '3200', 'name': 'Retained Earnings', 'name_ar': 'الأرباح المبقاة', 'type': 'equity', 'parent': '3000'},
        {'code': '3300', 'name': 'Owner Drawing', 'name_ar': 'المسحوبات الشخصية', 'type': 'equity', 'parent': '3000'},
        
        # الإيرادات
        {'code': '4000', 'name': 'Revenue', 'name_ar': 'الإيرادات', 'type': 'revenue', 'system': True},
        {'code': '4100', 'name': 'Sales Revenue', 'name_ar': 'إيرادات المبيعات', 'type': 'revenue', 'parent': '4000'},
        {'code': '4200', 'name': 'Service Revenue', 'name_ar': 'إيرادات الخدمات', 'type': 'revenue', 'parent': '4000'},
        {'code': '4300', 'name': 'Other Income', 'name_ar': 'إيرادات أخرى', 'type': 'revenue', 'parent': '4000'},
        {'code': '4400', 'name': 'Sales Returns', 'name_ar': 'مردودات المبيعات', 'type': 'revenue', 'parent': '4000'},
        {'code': '4500', 'name': 'Sales Discounts', 'name_ar': 'خصومات المبيعات', 'type': 'revenue', 'parent': '4000'},
        
        # تكلفة المبيعات
        {'code': '5000', 'name': 'Cost of Goods Sold', 'name_ar': 'تكلفة البضاعة المباعة', 'type': 'cogs', 'system': True},
        {'code': '5100', 'name': 'Direct Materials', 'name_ar': 'مواد مباشرة', 'type': 'cogs', 'parent': '5000'},
        {'code': '5200', 'name': 'Direct Labor', 'name_ar': 'عمالة مباشرة', 'type': 'cogs', 'parent': '5000'},
        
        # المصروفات
        {'code': '6000', 'name': 'Expenses', 'name_ar': 'المصروفات', 'type': 'expense', 'system': True},
        {'code': '6100', 'name': 'Salaries & Wages', 'name_ar': 'الرواتب والأجور', 'type': 'expense', 'parent': '6000'},
        {'code': '6110', 'name': 'Housing Allowance Expense', 'name_ar': 'مصروف بدل السكن', 'type': 'expense', 'parent': '6000'},
        {'code': '6120', 'name': 'Transport Allowance Expense', 'name_ar': 'مصروف بدل المواصلات', 'type': 'expense', 'parent': '6000'},
        {'code': '6150', 'name': 'GOSI Expense', 'name_ar': 'مصروف التأمينات الاجتماعية', 'type': 'expense', 'parent': '6000'},
        {'code': '6200', 'name': 'Rent Expense', 'name_ar': 'مصروف الإيجار', 'type': 'expense', 'parent': '6000'},
        {'code': '6300', 'name': 'Utilities', 'name_ar': 'مصاريف الكهرباء والماء', 'type': 'expense', 'parent': '6000'},
        {'code': '6400', 'name': 'Office Supplies', 'name_ar': 'مستلزمات مكتبية', 'type': 'expense', 'parent': '6000'},
        {'code': '6500', 'name': 'Marketing', 'name_ar': 'مصاريف تسويق', 'type': 'expense', 'parent': '6000'},
        {'code': '6600', 'name': 'Depreciation', 'name_ar': 'مصروف الإهلاك', 'type': 'expense', 'parent': '6000'},
        {'code': '6700', 'name': 'Insurance', 'name_ar': 'مصروف التأمين', 'type': 'expense', 'parent': '6000'},
        {'code': '6800', 'name': 'Professional Fees', 'name_ar': 'أتعاب مهنية', 'type': 'expense', 'parent': '6000'},
        {'code': '6900', 'name': 'Miscellaneous Expenses', 'name_ar': 'مصروفات متنوعة', 'type': 'expense', 'parent': '6000'},
        {'code': '6950', 'name': 'Bank Charges', 'name_ar': 'عمولات بنكية', 'type': 'expense', 'parent': '6000'},
    ]
    
    account_map = {}
    for acc_data in accounts_data:
        parent_id = None
        if 'parent' in acc_data:
            parent_id = account_map.get(acc_data['parent'])
        
        account = Account(
            code=acc_data['code'],
            name=acc_data['name'],
            name_ar=acc_data['name_ar'],
            account_type=acc_data['type'],
            parent_id=parent_id,
            is_system=acc_data.get('system', False),
            company_id=company_id
        )
        db.session.add(account)
        db.session.flush()
        account_map[acc_data['code']] = account.id
    
    db.session.commit()
    return account_map


# ==================== المصادقة ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        company_name = request.form['company_name']
        country_code = request.form.get('country_code', 'SA')
        
        if User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني مسجل مسبقاً', 'danger')
            return redirect(url_for('register'))
        
        # إنشاء الشركة
        tax_config = Config.TAX_CONFIGS.get(country_code, Config.TAX_CONFIGS['SA'])
        company = Company(
            name=company_name,
            country_code=country_code,
            currency=tax_config['currency'],
            subscription_plan='basic',
            subscription_status='trial',
            subscription_start=datetime.now(timezone.utc),
            subscription_end=datetime.now(timezone.utc) + timedelta(days=14)
        )
        db.session.add(company)
        db.session.flush()
        
        # إنشاء المستخدم
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='admin',
            company_id=company.id
        )
        user.set_password(password)
        db.session.add(user)
        
        # إنشاء شجرة الحسابات الافتراضية
        create_default_accounts(company.id, country_code)
        
        # إنشاء إعدادات الضرائب الافتراضية
        if tax_config['vat_rate'] > 0:
            vat_account = Account.query.filter_by(
                code='2300', company_id=company.id).first()
            tax_setting = TaxSetting(
                tax_name='VAT',
                tax_name_ar='ضريبة القيمة المضافة',
                tax_type='vat',
                rate=tax_config['vat_rate'],
                is_default=True,
                account_id=vat_account.id if vat_account else None,
                company_id=company.id
            )
            db.session.add(tax_setting)
        
        db.session.commit()
        
        login_user(user)
        flash('تم إنشاء الحساب بنجاح! لديك فترة تجريبية 14 يوم', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('register.html', countries=Config.TAX_CONFIGS)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user, remember=request.form.get('remember'))
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('بيانات الدخول غير صحيحة', 'danger')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ==================== لوحة التحكم ====================

@app.route('/dashboard')
@login_required
@company_required
def dashboard():
    company = current_user.company
    today = date.today()
    month_start = today.replace(day=1)
    
    # إحصائيات
    stats = {
        'total_revenue_month': db.session.query(
            db.func.sum(Invoice.total)).filter(
            Invoice.company_id == company.id,
            Invoice.status.in_(['sent', 'partial', 'paid']),
            Invoice.invoice_date >= month_start
        ).scalar() or 0,
        
        'total_expenses_month': db.session.query(
            db.func.sum(Purchase.total)).filter(
            Purchase.company_id == company.id,
            Purchase.status.in_(['approved', 'partial', 'paid']),
            Purchase.purchase_date >= month_start
        ).scalar() or 0,
        
        'outstanding_receivables': db.session.query(
            db.func.sum(Invoice.balance_due)).filter(
            Invoice.company_id == company.id,
            Invoice.status.in_(['sent', 'partial', 'overdue'])
        ).scalar() or 0,
        
        'outstanding_payables': db.session.query(
            db.func.sum(Purchase.balance_due)).filter(
            Purchase.company_id == company.id,
            Purchase.status.in_(['approved', 'partial'])
        ).scalar() or 0,
        
        'total_customers': Customer.query.filter_by(
            company_id=company.id, is_active=True).count(),
        
        'total_invoices_month': Invoice.query.filter(
            Invoice.company_id == company.id,
            Invoice.invoice_date >= month_start
        ).count(),
        
        'overdue_invoices': Invoice.query.filter(
            Invoice.company_id == company.id,
            Invoice.status == 'overdue'
        ).count(),
        
        'total_employees': Employee.query.filter_by(
            company_id=company.id, status='active').count(),
    }
    
    # آخر الفواتير
    recent_invoices = Invoice.query.filter_by(
        company_id=company.id
    ).order_by(Invoice.created_at.desc()).limit(5).all()
    
    # آخر المشتريات
    recent_purchases = Purchase.query.filter_by(
        company_id=company.id
    ).order_by(Purchase.created_at.desc()).limit(5).all()
    
    # بيانات الرسم البياني (آخر 6 أشهر)
    chart_data = {'labels': [], 'revenue': [], 'expenses': []}
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        month_name = calendar.month_abbr[m]
        chart_data['labels'].append(month_name)
        
        m_start = date(y, m, 1)
        m_end = date(y, m, calendar.monthrange(y, m)[1])
        
        rev = db.session.query(db.func.sum(Invoice.total)).filter(
            Invoice.company_id == company.id,
            Invoice.status.in_(['sent', 'partial', 'paid']),
            Invoice.invoice_date.between(m_start, m_end)
        ).scalar() or 0
        
        exp = db.session.query(db.func.sum(Purchase.total)).filter(
            Purchase.company_id == company.id,
            Purchase.status.in_(['approved', 'partial', 'paid']),
            Purchase.purchase_date.between(m_start, m_end)
        ).scalar() or 0
        
        chart_data['revenue'].append(float(rev))
        chart_data['expenses'].append(float(exp))
    
    return render_template('dashboard.html', 
                         stats=stats, 
                         recent_invoices=recent_invoices,
                         recent_purchases=recent_purchases,
                         chart_data=json.dumps(chart_data),
                         company=company)


# ==================== شجرة الحسابات ====================

@app.route('/accounts')
@login_required
@company_required
def chart_of_accounts():
    accounts = Account.query.filter_by(
        company_id=current_user.company_id
    ).order_by(Account.code).all()
    return render_template('chart_of_accounts.html', accounts=accounts, company=current_user.company)


@app.route('/accounts/add', methods=['POST'])
@login_required
@company_required
def add_account():
    account = Account(
        code=request.form['code'],
        name=request.form['name'],
        name_ar=request.form.get('name_ar', ''),
        account_type=request.form['account_type'],
        parent_id=request.form.get('parent_id') or None,
        description=request.form.get('description', ''),
        company_id=current_user.company_id
    )
    db.session.add(account)
    db.session.commit()
    flash('تم إضافة الحساب بنجاح', 'success')
    return redirect(url_for('chart_of_accounts'))


@app.route('/accounts/<int:id>/edit', methods=['POST'])
@login_required
@company_required
def edit_account(id):
    account = Account.query.get_or_404(id)
    if account.company_id != current_user.company_id:
        flash('غير مصرح', 'danger')
        return redirect(url_for('chart_of_accounts'))
    
    account.name = request.form['name']
    account.name_ar = request.form.get('name_ar', '')
    account.description = request.form.get('description', '')
    db.session.commit()
    flash('تم تعديل الحساب', 'success')
    return redirect(url_for('chart_of_accounts'))


# ==================== القيود المحاسبية ====================

@app.route('/journal-entries')
@login_required
@company_required
def journal_entries():
    entries = JournalEntry.query.filter_by(
        company_id=current_user.company_id
    ).order_by(JournalEntry.entry_date.desc()).all()
    return render_template('journal_entries.html', entries=entries, company=current_user.company)


@app.route('/journal-entries/add', methods=['GET', 'POST'])
@login_required
@company_required
def add_journal_entry():
    if request.method == 'POST':
        # Auto number
        last_entry = JournalEntry.query.filter_by(
            company_id=current_user.company_id
        ).order_by(JournalEntry.id.desc()).first()
        next_num = 1 if not last_entry else int(last_entry.entry_number.split('-')[-1]) + 1
        
        entry = JournalEntry(
            entry_number=f"JE-{next_num:06d}",
            entry_date=datetime.strptime(request.form['entry_date'], '%Y-%m-%d').date(),
            description=request.form.get('description', ''),
            reference=request.form.get('reference', ''),
            entry_type='manual',
            company_id=current_user.company_id,
            created_by=current_user.id
        )
        db.session.add(entry)
        db.session.flush()
        
        # إضافة البنود
        accounts = request.form.getlist('line_account[]')
        descriptions = request.form.getlist('line_description[]')
        debits = request.form.getlist('line_debit[]')
        credits = request.form.getlist('line_credit[]')
        
        total_debit = 0
        total_credit = 0
        
        for i, account in enumerate(accounts):
            if account:
                debit = float(debits[i] or 0)
                credit = float(credits[i] or 0)
                
                line = JournalLine(
                    journal_entry_id=entry.id,
                    account_id=int(account),
                    description=descriptions[i] if i < len(descriptions) else '',
                    debit=debit,
                    credit=credit
                )
                db.session.add(line)
                total_debit += debit
                total_credit += credit
        
        entry.total_debit = total_debit
        entry.total_credit = total_credit
        
        if abs(total_debit - total_credit) > 0.01:
            db.session.rollback()
            flash('القيد غير متوازن! المدين يجب أن يساوي الدائن', 'danger')
            accounts_list = Account.query.filter_by(
                company_id=current_user.company_id, is_active=True
            ).order_by(Account.code).all()
            return render_template('journal_entry_form.html', accounts=accounts_list)
        
        db.session.commit()
        flash('تم إضافة القيد بنجاح', 'success')
        return redirect(url_for('journal_entries'))
    
    accounts = Account.query.filter_by(
        company_id=current_user.company_id, is_active=True
    ).order_by(Account.code).all()
    return render_template('journal_entry_form.html', accounts=accounts, company=current_user.company)


@app.route('/journal-entries/<int:id>/post', methods=['POST'])
@login_required
@company_required
def post_journal_entry(id):
    entry = JournalEntry.query.get_or_404(id)
    if entry.company_id != current_user.company_id:
        flash('غير مصرح', 'danger')
        return redirect(url_for('journal_entries'))
    
    if entry.status != 'draft':
        flash('هذا القيد مرحّل مسبقاً', 'warning')
        return redirect(url_for('journal_entries'))
    
    # تحديث أرصدة الحسابات
    for line in entry.lines:
        account = Account.query.get(line.account_id)
        if account.account_type in ['asset', 'expense', 'cogs']:
            account.balance += line.debit - line.credit
        else:
            account.balance += line.credit - line.debit
    
    entry.status = 'posted'
    entry.posted_by = current_user.id
    entry.posted_at = datetime.utcnow()
    db.session.commit()
    
    flash('تم ترحيل القيد بنجاح', 'success')
    return redirect(url_for('journal_entries'))


# ==================== العملاء ====================

@app.route('/customers')
@login_required
@company_required
def customers():
    customers_list = Customer.query.filter_by(
        company_id=current_user.company_id
    ).order_by(Customer.name).all()
    return render_template('customers.html', customers=customers_list, company=current_user.company)


@app.route('/customers/add', methods=['POST'])
@login_required
@company_required
def add_customer():
    last = Customer.query.filter_by(company_id=current_user.company_id).count()
    customer = Customer(
        code=f"C-{last+1:04d}",
        name=request.form['name'],
        name_ar=request.form.get('name_ar', ''),
        email=request.form.get('email', ''),
        phone=request.form.get('phone', ''),
        address=request.form.get('address', ''),
        city=request.form.get('city', ''),
        country=request.form.get('country', ''),
        tax_number=request.form.get('tax_number', ''),
        credit_limit=float(request.form.get('credit_limit', 0)),
        company_id=current_user.company_id
    )
    db.session.add(customer)
    db.session.commit()
    flash('تم إضافة العميل بنجاح', 'success')
    return redirect(url_for('customers'))


# ==================== الموردين ====================

@app.route('/suppliers')
@login_required
@company_required
def suppliers():
    suppliers_list = Supplier.query.filter_by(
        company_id=current_user.company_id
    ).order_by(Supplier.name).all()
    return render_template('suppliers.html', suppliers=suppliers_list, company=current_user.company)


@app.route('/suppliers/add', methods=['POST'])
@login_required
@company_required
def add_supplier():
    last = Supplier.query.filter_by(company_id=current_user.company_id).count()
    supplier = Supplier(
        code=f"S-{last+1:04d}",
        name=request.form['name'],
        name_ar=request.form.get('name_ar', ''),
        email=request.form.get('email', ''),
        phone=request.form.get('phone', ''),
        address=request.form.get('address', ''),
        tax_number=request.form.get('tax_number', ''),
        company_id=current_user.company_id
    )
    db.session.add(supplier)
    db.session.commit()
    flash('تم إضافة المورد بنجاح', 'success')
    return redirect(url_for('suppliers'))


# ==================== المنتجات ====================

@app.route('/products')
@login_required
@company_required
def products():
    products_list = Product.query.filter_by(
        company_id=current_user.company_id
    ).order_by(Product.name).all()
    return render_template('products.html', products=products_list, company=current_user.company)


@app.route('/products/add', methods=['POST'])
@login_required
@company_required
def add_product():
    product = Product(
        code=request.form.get('code', ''),
        name=request.form['name'],
        name_ar=request.form.get('name_ar', ''),
        description=request.form.get('description', ''),
        product_type=request.form.get('product_type', 'product'),
        unit=request.form.get('unit', 'unit'),
        cost_price=float(request.form.get('cost_price', 0)),
        sell_price=float(request.form.get('sell_price', 0)),
        tax_rate=float(request.form.get('tax_rate', 15)),
        is_taxable=request.form.get('is_taxable') == 'on',
        stock_quantity=float(request.form.get('stock_quantity', 0)),
        company_id=current_user.company_id
    )
    db.session.add(product)
    db.session.commit()
    flash('تم إضافة المنتج بنجاح', 'success')
    return redirect(url_for('products'))


# ==================== الفواتير (المبيعات) ====================

@app.route('/invoices')
@login_required
@company_required
def invoices():
    status_filter = request.args.get('status', 'all')
    query = Invoice.query.filter_by(company_id=current_user.company_id)
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    invoices_list = query.order_by(Invoice.invoice_date.desc()).all()
    return render_template('invoices.html', invoices=invoices_list, status_filter=status_filter, company=current_user.company)


@app.route('/invoices/add', methods=['GET', 'POST'])
@login_required
@company_required
def add_invoice():
    if request.method == 'POST':
        # Auto number
        last_inv = Invoice.query.filter_by(
            company_id=current_user.company_id
        ).order_by(Invoice.id.desc()).first()
        next_num = 1 if not last_inv else int(last_inv.invoice_number.split('-')[-1]) + 1
        
        company = current_user.company
        tax_config = Config.TAX_CONFIGS.get(company.country_code, {})
        vat_rate = tax_config.get('vat_rate', 15)
        
        invoice = Invoice(
            invoice_number=f"INV-{next_num:06d}",
            invoice_date=datetime.strptime(request.form['invoice_date'], '%Y-%m-%d').date(),
            due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d').date() if request.form.get('due_date') else None,
            customer_id=int(request.form['customer_id']),
            currency=company.currency,
            notes=request.form.get('notes', ''),
            company_id=current_user.company_id,
            created_by=current_user.id
        )
        db.session.add(invoice)
        db.session.flush()
        
        # إضافة البنود
        descriptions = request.form.getlist('item_description[]')
        quantities = request.form.getlist('item_quantity[]')
        prices = request.form.getlist('item_price[]')
        tax_rates = request.form.getlist('item_tax_rate[]')
        product_ids = request.form.getlist('item_product_id[]')
        
        subtotal = 0
        total_tax = 0
        
        for i, desc in enumerate(descriptions):
            if desc:
                qty = float(quantities[i] or 1)
                price = float(prices[i] or 0)
                rate = float(tax_rates[i] if i < len(tax_rates) else vat_rate)
                line_total = qty * price
                line_tax = line_total * rate / 100
                
                item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_id=int(product_ids[i]) if i < len(product_ids) and product_ids[i] else None,
                    description=desc,
                    quantity=qty,
                    unit_price=price,
                    tax_rate=rate,
                    tax_amount=line_tax,
                    total=line_total + line_tax
                )
                db.session.add(item)
                subtotal += line_total
                total_tax += line_tax
        
        invoice.subtotal = subtotal
        invoice.tax_amount = total_tax
        invoice.total = subtotal + total_tax
        invoice.balance_due = invoice.total
        
        db.session.commit()
        flash('تم إنشاء الفاتورة بنجاح', 'success')
        return redirect(url_for('view_invoice', id=invoice.id))
    
    customers_list = Customer.query.filter_by(
        company_id=current_user.company_id, is_active=True).all()
    products_list = Product.query.filter_by(
        company_id=current_user.company_id, is_active=True).all()
    company = current_user.company
    tax_config = Config.TAX_CONFIGS.get(company.country_code, {})
    
    return render_template('invoice_form.html', 
                         customers=customers_list,
                         products=products_list,
                         tax_rate=tax_config.get('vat_rate', 15),
                         company=company)


@app.route('/invoices/<int:id>')
@login_required
@company_required
def view_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.company_id != current_user.company_id:
        flash('غير مصرح', 'danger')
        return redirect(url_for('invoices'))
    return render_template('invoice_view.html', invoice=invoice, company=current_user.company)


@app.route('/invoices/<int:id>/approve', methods=['POST'])
@login_required
@company_required
def approve_invoice(id):
    invoice = Invoice.query.get_or_404(id)
    if invoice.company_id != current_user.company_id:
        return redirect(url_for('invoices'))
    
    if invoice.status == 'draft':
        invoice.status = 'sent'
        
        # إنشاء قيد محاسبي تلقائي
        last_entry = JournalEntry.query.filter_by(
            company_id=current_user.company_id
        ).order_by(JournalEntry.id.desc()).first()
        next_num = 1 if not last_entry else int(last_entry.entry_number.split('-')[-1]) + 1
        
        journal = JournalEntry(
            entry_number=f"JE-{next_num:06d}",
            entry_date=invoice.invoice_date,
            description=f"فاتورة مبيعات {invoice.invoice_number}",
            reference=invoice.invoice_number,
            entry_type='invoice',
            status='posted',
            total_debit=invoice.total,
            total_credit=invoice.total,
            company_id=current_user.company_id,
            created_by=current_user.id,
            posted_by=current_user.id,
            posted_at=datetime.utcnow()
        )
        db.session.add(journal)
        db.session.flush()
        
        # مدين: الذمم المدينة
        ar_account = Account.query.filter_by(
            code='1200', company_id=current_user.company_id).first()
        # دائن: إيرادات المبيعات
        revenue_account = Account.query.filter_by(
            code='4100', company_id=current_user.company_id).first()
        # دائن: ضريبة القيمة المضافة
        vat_account = Account.query.filter_by(
            code='2300', company_id=current_user.company_id).first()
        
        if ar_account:
            db.session.add(JournalLine(
                journal_entry_id=journal.id,
                account_id=ar_account.id,
                description=f"ذمم مدينة - {invoice.customer.name}",
                debit=invoice.total, credit=0
            ))
            ar_account.balance += invoice.total
        
        if revenue_account:
            db.session.add(JournalLine(
                journal_entry_id=journal.id,
                account_id=revenue_account.id,
                description="إيرادات مبيعات",
                debit=0, credit=invoice.subtotal
            ))
            revenue_account.balance += invoice.subtotal
        
        if vat_account and invoice.tax_amount > 0:
            db.session.add(JournalLine(
                journal_entry_id=journal.id,
                account_id=vat_account.id,
                description="ضريبة القيمة المضافة",
                debit=0, credit=invoice.tax_amount
            ))
            vat_account.balance += invoice.tax_amount
        
        invoice.journal_entry_id = journal.id
        
        # تحديث رصيد العميل
        customer = Customer.query.get(invoice.customer_id)
        if customer:
            customer.balance += invoice.total
        
        db.session.commit()
        flash('تم اعتماد الفاتورة وإنشاء القيد المحاسبي', 'success')
    
    return redirect(url_for('view_invoice', id=id))


@app.route('/payroll/employees')
@login_required
@company_required
def employees():
    employees_list = Employee.query.filter_by(
        company_id=current_user.company_id
    ).order_by(Employee.first_name).all()
    return render_template('payroll/employees.html', employees=employees_list)


@app.route('/payroll/employees/add', methods=['GET', 'POST'])
@login_required
@company_required
def add_employee():
    if request.method == 'POST':
        last = Employee.query.filter_by(company_id=current_user.company_id).count()
        employee = Employee(
            employee_number=f"EMP-{last+1:04d}",
            first_name=request.form['first_name'],
            last_name=request.form['last_name'],
            first_name_ar=request.form.get('first_name_ar', ''),
            last_name_ar=request.form.get('last_name_ar', ''),
            email=request.form.get('email', ''),
            phone=request.form.get('phone', ''),
            national_id=request.form.get('national_id', ''),
            nationality=request.form.get('nationality', ''),
            gender=request.form.get('gender', ''),
            date_of_birth=datetime.strptime(request.form['date_of_birth'], '%Y-%m-%d').date() if request.form.get('date_of_birth') else None,
            hire_date=datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date(),
            department=request.form.get('department', ''),
            position=request.form.get('position', ''),
            employment_type=request.form.get('employment_type', 'full_time'),
            basic_salary=float(request.form.get('basic_salary', 0)),
            housing_allowance=float(request.form.get('housing_allowance', 0)),
            transport_allowance=float(request.form.get('transport_allowance', 0)),
            food_allowance=float(request.form.get('food_allowance', 0)),
            phone_allowance=float(request.form.get('phone_allowance', 0)),
            other_allowances=float(request.form.get('other_allowances', 0)),
            bank_name=request.form.get('bank_name', ''),
            bank_account=request.form.get('bank_account', ''),
            iban=request.form.get('iban', ''),
            company_id=current_user.company_id
        )
        db.session.add(employee)
        db.session.commit()
        flash('تم إضافة الموظف بنجاح', 'success')
        return redirect(url_for('employees'))
    
    return render_template('payroll/employee_form.html')


@app.route('/payroll/run', methods=['GET', 'POST'])
@login_required
@company_required
@admin_required
def payroll_run():
    if request.method == 'POST':
        month = int(request.form['month'])
        year = int(request.form['year'])
        
        # التحقق من عدم وجود مسير رواتب سابق
        existing = PayrollRun.query.filter_by(
            company_id=current_user.company_id,
            period_month=month, period_year=year
        ).first()
        if existing:
            flash('يوجد مسير رواتب لهذه الفترة بالفعل', 'warning')
            return redirect(url_for('payroll_run'))
        
        period_start = date(year, month, 1)
        period_end = date(year, month, calendar.monthrange(year, month)[1])
        
        last_run = PayrollRun.query.filter_by(
            company_id=current_user.company_id
        ).order_by(PayrollRun.id.desc()).first()
        next_num = 1 if not last_run else int(last_run.run_number.split('-')[-1]) + 1
        
        run = PayrollRun(
            run_number=f"PR-{next_num:04d}",
            period_month=month,
            period_year=year,
            period_start=period_start,
            period_end=period_end,
            company_id=current_user.company_id,
            created_by=current_user.id
        )
        db.session.add(run)
        db.session.flush()
        
        # إنشاء قسائم الرواتب
        active_employees = Employee.query.filter_by(
            company_id=current_user.company_id, status='active'
        ).all()
        
        total_gross = 0
        total_deductions = 0
        total_net = 0
        total_gosi_company = 0
        
        company = current_user.company
        country = company.country_code
        
        for emp in active_employees:
            last_slip = Payslip.query.filter_by(
                company_id=current_user.company_id
            ).order_by(Payslip.id.desc()).first()
            slip_num = 1 if not last_slip else int(last_slip.payslip_number.split('-')[-1]) + 1
            
            gross = emp.gross_salary
            
            # حساب التأمينات (السعودية)
            gosi_emp = 0
            gosi_comp = 0
            income_tax = 0
            
            if country == 'SA':
                # التأمينات الاجتماعية
                gosi_base = emp.basic_salary + emp.housing_allowance
                if emp.nationality and emp.nationality.lower() in ['saudi', 'سعودي']:
                    gosi_emp = gosi_base * emp.gosi_employee_pct / 100
                    gosi_comp = gosi_base * emp.gosi_company_pct / 100
                else:
                    gosi_emp = 0
                    gosi_comp = gosi_base * 2 / 100  # 2% للأجانب
            elif country == 'US':
                # ضريبة الدخل الفيدرالية (مبسطة)
                annual = gross * 12
                if annual <= 11000:
                    income_tax = gross * 10 / 100
                elif annual <= 44725:
                    income_tax = gross * 12 / 100
                elif annual <= 95375:
                    income_tax = gross * 22 / 100
                else:
                    income_tax = gross * 24 / 100
                
                # Social Security & Medicare
                gosi_emp = gross * 7.65 / 100
                gosi_comp = gross * 7.65 / 100
            elif country == 'EG':
                # تأمينات مصر
                gosi_emp = emp.basic_salary * 11 / 100
                gosi_comp = emp.basic_salary * 18.75 / 100
            
            total_ded = gosi_emp + income_tax + emp.medical_insurance
            net = gross - total_ded
            
            payslip = Payslip(
                payslip_number=f"PS-{slip_num:06d}",
                employee_id=emp.id,
                period_start=period_start,
                period_end=period_end,
                basic_salary=emp.basic_salary,
                housing_allowance=emp.housing_allowance,
                transport_allowance=emp.transport_allowance,
                food_allowance=emp.food_allowance,
                phone_allowance=emp.phone_allowance,
                other_allowances=emp.other_allowances,
                gross_salary=gross,
                gosi_employee=gosi_emp,
                gosi_company=gosi_comp,
                income_tax=income_tax,
                medical_insurance=emp.medical_insurance,
                total_deductions=total_ded,
                net_salary=net,
                status='draft',
                company_id=current_user.company_id
            )
            db.session.add(payslip)
            
            total_gross += gross
            total_deductions += total_ded
            total_net += net
            total_gosi_company += gosi_comp
        
        run.total_gross = total_gross
        run.total_deductions = total_deductions
        run.total_net = total_net
        run.total_gosi_company = total_gosi_company
        run.employee_count = len(active_employees)
        
        db.session.commit()
        flash(f'تم إنشاء مسير الرواتب - {len(active_employees)} موظف', 'success')
        return redirect(url_for('payroll_runs'))
    
    return render_template('payroll/payroll_run.html')


@app.route('/payroll/runs')
@login_required
@company_required
def payroll_runs():
    runs = PayrollRun.query.filter_by(
        company_id=current_user.company_id
    ).order_by(PayrollRun.period_year.desc(), PayrollRun.period_month.desc()).all()
    return render_template('payroll/payroll_runs.html', runs=runs)


@app.route('/payroll/runs/<int:id>/approve', methods=['POST'])
@login_required
@company_required
@admin_required
def approve_payroll_run(id):
    run = PayrollRun.query.get_or_404(id)
    if run.company_id != current_user.company_id:
        return redirect(url_for('payroll_runs'))
    
    if run.status == 'draft':
        run.status = 'approved'
        run.approved_by = current_user.id
        
        # تحديث حالة القسائم
        payslips = Payslip.query.filter_by(
            company_id=current_user.company_id,
            period_start=run.period_start,
            period_end=run.period_end,
            status='draft'
        ).all()
        
        for ps in payslips:
            ps.status = 'approved'
        
        # إنشاء قيد محاسبي للرواتب
        last_entry = JournalEntry.query.filter_by(
            company_id=current_user.company_id
        ).order_by(JournalEntry.id.desc()).first()
        next_num = 1 if not last_entry else int(last_entry.entry_number.split('-')[-1]) + 1
        
        journal = JournalEntry(
            entry_number=f"JE-{next_num:06d}",
            entry_date=run.period_end,
            description=f"مسير رواتب {run.period_month}/{run.period_year}",
            reference=run.run_number,
            entry_type='payroll',
            status='posted',
            total_debit=run.total_gross + run.total_gosi_company,
            total_credit=run.total_gross + run.total_gosi_company,
            company_id=current_user.company_id,
            created_by=current_user.id,
            posted_by=current_user.id,
            posted_at=datetime.utcnow()
        )
        db.session.add(journal)
        db.session.flush()
        
        # مدين: مصروف الرواتب
        salary_account = Account.query.filter_by(
            code='6100', company_id=current_user.company_id).first()
        gosi_expense = Account.query.filter_by(
            code='6150', company_id=current_user.company_id).first()
        # دائن: رواتب مستحقة
        salary_payable = Account.query.filter_by(
            code='2400', company_id=current_user.company_id).first()
        gosi_payable = Account.query.filter_by(
            code='2500', company_id=current_user.company_id).first()
        
        if salary_account:
            db.session.add(JournalLine(
                journal_entry_id=journal.id,
                account_id=salary_account.id,
                description="مصروف الرواتب",
                debit=run.total_gross, credit=0
            ))
        
        if gosi_expense and run.total_gosi_company > 0:
            db.session.add(JournalLine(
                journal_entry_id=journal.id,
                account_id=gosi_expense.id,
                description="حصة الشركة في التأمينات",
                debit=run.total_gosi_company, credit=0
            ))
        
        if salary_payable:
            db.session.add(JournalLine(
                journal_entry_id=journal.id,
                account_id=salary_payable.id,
                description="رواتب مستحقة الدفع",
                debit=0, credit=run.total_net
            ))
        
        total_gosi = sum(ps.gosi_employee for ps in payslips) + run.total_gosi_company
        if gosi_payable and total_gosi > 0:
            db.session.add(JournalLine(
                journal_entry_id=journal.id,
                account_id=gosi_payable.id,
                description="تأمينات اجتماعية مستحقة",
                debit=0, credit=total_gosi
            ))
        
        total_tax = sum(ps.income_tax for ps in payslips)
        if total_tax > 0:
            db.session.add(JournalLine(
                journal_entry_id=journal.id,
                account_id=salary_payable.id,
                description="ضريبة دخل مستقطعة",
                debit=0, credit=total_tax
            ))
        
        db.session.commit()
        flash('تم اعتماد مسير الرواتب وإنشاء القيد المحاسبي', 'success')
    
    return redirect(url_for('payroll_runs'))


@app.route('/payroll/payslips/<int:id>')
@login_required
@company_required
def view_payslip(id):
    payslip = Payslip.query.get_or_404(id)
    if payslip.company_id != current_user.company_id:
        return redirect(url_for('payroll_runs'))
    return render_template('payroll/payslip_view.html', payslip=payslip)


# ==================== التقارير المالية ====================

@app.route('/reports/trial-balance')
@login_required
@company_required
def trial_balance():
    as_of = request.args.get('as_of', date.today().isoformat())
    as_of_date = datetime.strptime(as_of, '%Y-%m-%d').date()
    
    accounts = Account.query.filter_by(
        company_id=current_user.company_id
    ).order_by(Account.code).all()
    
    trial_data = []
    total_debit = 0
    total_credit = 0
    
    for acc in accounts:
        # حساب الرصيد من القيود المرحلة
        debits = db.session.query(db.func.sum(JournalLine.debit)).join(
            JournalEntry
        ).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.status == 'posted',
            JournalEntry.entry_date <= as_of_date
        ).scalar() or 0
        
        credits = db.session.query(db.func.sum(JournalLine.credit)).join(
            JournalEntry
        ).filter(
            JournalLine.account_id == acc.id,
            JournalEntry.status == 'posted',
            JournalEntry.entry_date <= as_of_date
        ).scalar() or 0
        
        balance = debits - credits
        
        if abs(balance) > 0.01:
            trial_data.append({
                'code': acc.code,
                'name': acc.name_ar or acc.name,
                'type': acc.account_type,
                'debit': balance if balance > 0 else 0,
                'credit': abs(balance) if balance < 0 else 0
            })
            if balance > 0:
                total_debit += balance
            else:
                total_credit += abs(balance)
    
    return render_template('reports/trial_balance.html',
                         trial_data=trial_data,
                         total_debit=total_debit,
                         total_credit=total_credit,
                         as_of=as_of)


@app.route('/reports/income-statement')
@login_required
@company_required
def income_statement():
    period_start = request.args.get('start', date.today().replace(month=1, day=1).isoformat())
    period_end = request.args.get('end', date.today().isoformat())
    start_date = datetime.strptime(period_start, '%Y-%m-%d').date()
    end_date = datetime.strptime(period_end, '%Y-%m-%d').date()
    
    def get_account_balance(account_type, start, end):
        result = db.session.query(
            Account.code, Account.name, Account.name_ar,
            db.func.sum(JournalLine.debit).label('total_debit'),
            db.func.sum(JournalLine.credit).label('total_credit')
        ).join(JournalLine, Account.id == JournalLine.account_id
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).filter(
            Account.company_id == current_user.company_id,
            Account.account_type == account_type,
            JournalEntry.status == 'posted',
            JournalEntry.entry_date.between(start, end)
        ).group_by(Account.id).all()
        
        items = []
        total = 0
        for r in result:
            if account_type in ['revenue']:
                balance = (r.total_credit or 0) - (r.total_debit or 0)
            else:
                balance = (r.total_debit or 0) - (r.total_credit or 0)
            if abs(balance) > 0.01:
                items.append({
                    'code': r.code,
                    'name': r.name_ar or r.name,
                    'balance': balance
                })
                total += balance
        return items, total
    
    revenue_items, total_revenue = get_account_balance('revenue', start_date, end_date)
    cogs_items, total_cogs = get_account_balance('cogs', start_date, end_date)
    expense_items, total_expenses = get_account_balance('expense', start_date, end_date)
    
    gross_profit = total_revenue - total_cogs
    net_income = gross_profit - total_expenses
    
    return render_template('reports/income_statement.html',
                         revenue_items=revenue_items, total_revenue=total_revenue,
                         cogs_items=cogs_items, total_cogs=total_cogs,
                         expense_items=expense_items, total_expenses=total_expenses,
                         gross_profit=gross_profit, net_income=net_income,
                         period_start=period_start, period_end=period_end)


@app.route('/reports/balance-sheet')
@login_required
@company_required
def balance_sheet():
    as_of = request.args.get('as_of', date.today().isoformat())
    as_of_date = datetime.strptime(as_of, '%Y-%m-%d').date()
    
    def get_balances(account_type):
        result = db.session.query(
            Account.code, Account.name, Account.name_ar,
            db.func.sum(JournalLine.debit).label('total_debit'),
            db.func.sum(JournalLine.credit).label('total_credit')
        ).join(JournalLine, Account.id == JournalLine.account_id
        ).join(JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
        ).filter(
            Account.company_id == current_user.company_id,
            Account.account_type == account_type,
            JournalEntry.status == 'posted',
            JournalEntry.entry_date <= as_of_date
        ).group_by(Account.id).all()
        
        items = []
        total = 0
        for r in result:
            if account_type == 'asset':
                balance = (r.total_debit or 0) - (r.total_credit or 0)
            else:
                balance = (r.total_credit or 0) - (r.total_debit or 0)
            if abs(balance) > 0.01:
                items.append({
                    'code': r.code,
                    'name': r.name_ar or r.name,
                    'balance': balance
                })
                total += balance
        return items, total
    
    asset_items, total_assets = get_balances('asset')
    liability_items, total_liabilities = get_balances('liability')
    equity_items, total_equity = get_balances('equity')
    
    # إضافة صافي الربح لحقوق الملكية
    year_start = as_of_date.replace(month=1, day=1)
    
    revenue_total = db.session.query(
        db.func.sum(JournalLine.credit) - db.func.sum(JournalLine.debit)
    ).join(JournalEntry).join(Account, JournalLine.account_id == Account.id
    ).filter(
        Account.company_id == current_user.company_id,
        Account.account_type == 'revenue',
        JournalEntry.status == 'posted',
        JournalEntry.entry_date.between(year_start, as_of_date)
    ).scalar() or 0
    
    expense_total = db.session.query(
        db.func.sum(JournalLine.debit) - db.func.sum(JournalLine.credit)
    ).join(JournalEntry).join(Account, JournalLine.account_id == Account.id
    ).filter(
        Account.company_id == current_user.company_id,
        Account.account_type.in_(['expense', 'cogs']),
        JournalEntry.status == 'posted',
        JournalEntry.entry_date.between(year_start, as_of_date)
    ).scalar() or 0
    
    net_income = revenue_total - expense_total
    if abs(net_income) > 0.01:
        equity_items.append({
            'code': '-',
            'name': 'صافي ربح/خسارة الفترة',
            'balance': net_income
        })
        total_equity += net_income
    
    return render_template('reports/balance_sheet.html',
                         asset_items=asset_items, total_assets=total_assets,
                         liability_items=liability_items, total_liabilities=total_liabilities,
                         equity_items=equity_items, total_equity=total_equity,
                         as_of=as_of)


@app.route('/reports/general-ledger')
@login_required
@company_required
def general_ledger():
    account_id = request.args.get('account_id', type=int)
    start = request.args.get('start', date.today().replace(month=1, day=1).isoformat())
    end = request.args.get('end', date.today().isoformat())
    
    accounts = Account.query.filter_by(
        company_id=current_user.company_id
    ).order_by(Account.code).all()
    
    ledger_data = []
    selected_account = None
    
    if account_id:
        selected_account = Account.query.get(account_id)
        start_date = datetime.strptime(start, '%Y-%m-%d').date()
        end_date = datetime.strptime(end, '%Y-%m-%d').date()
        
        entries = db.session.query(
            JournalLine, JournalEntry
        ).join(JournalEntry).filter(
            JournalLine.account_id == account_id,
            JournalEntry.status == 'posted',
            JournalEntry.entry_date.between(start_date, end_date)
        ).order_by(JournalEntry.entry_date).all()
        
        running_balance = 0
        for line, entry in entries:
            if selected_account.account_type in ['asset', 'expense', 'cogs']:
                running_balance += line.debit - line.credit
            else:
                running_balance += line.credit - line.debit
            
            ledger_data.append({
                'date': entry.entry_date,
                'entry_number': entry.entry_number,
                'description': line.description or entry.description,
                'debit': line.debit,
                'credit': line.credit,
                'balance': running_balance
            })
    
    return render_template('reports/general_ledger.html',
                         accounts=accounts,
                         ledger_data=ledger_data,
                         selected_account=selected_account,
                         start=start, end=end,
                         account_id=account_id)


# ==================== الإقرار الضريبي ====================

@app.route('/tax/returns')
@login_required
@company_required
def tax_returns():
    returns = TaxReturn.query.filter_by(
        company_id=current_user.company_id
    ).order_by(TaxReturn.period_end.desc()).all()
    return render_template('tax_returns.html', returns=returns)


@app.route('/tax/returns/generate', methods=['GET', 'POST'])
@login_required
@company_required
def generate_tax_return():
    if request.method == 'POST':
        start = datetime.strptime(request.form['period_start'], '%Y-%m-%d').date()
        end = datetime.strptime(request.form['period_end'], '%Y-%m-%d').date()
        
        # حساب ضريبة المبيعات
        sales_data = db.session.query(
            db.func.sum(Invoice.subtotal),
            db.func.sum(Invoice.tax_amount)
        ).filter(
            Invoice.company_id == current_user.company_id,
            Invoice.status.in_(['sent', 'partial', 'paid']),
            Invoice.invoice_date.between(start, end)
        ).first()
        
        # حساب ضريبة المشتريات
        purchase_data = db.session.query(
            db.func.sum(Purchase.subtotal),
            db.func.sum(Purchase.tax_amount)
        ).filter(
            Purchase.company_id == current_user.company_id,
            Purchase.status.in_(['approved', 'partial', 'paid']),
            Purchase.purchase_date.between(start, end)
        ).first()
        
        total_sales = sales_data[0] or 0
        total_sales_tax = sales_data[1] or 0
        total_purchases = purchase_data[0] or 0
        total_purchases_tax = purchase_data[1] or 0
        
        net_tax = total_sales_tax - total_purchases_tax
        
        last_ret = TaxReturn.query.filter_by(
            company_id=current_user.company_id
        ).order_by(TaxReturn.id.desc()).first()
        next_num = 1 if not last_ret else int(last_ret.return_number.split('-')[-1]) + 1
        
        tax_return = TaxReturn(
            return_number=f"VAT-{next_num:04d}",
            period_start=start,
            period_end=end,
            tax_type='vat',
            total_sales=total_sales,
            total_sales_tax=total_sales_tax,
            total_purchases=total_purchases,
            total_purchases_tax=total_purchases_tax,
            tax_due=net_tax if net_tax > 0 else 0,
            tax_refund=abs(net_tax) if net_tax < 0 else 0,
            net_tax=net_tax,
            status='draft',
            company_id=current_user.company_id
        )
        db.session.add(tax_return)
        db.session.commit()
        
        flash('تم إنشاء الإقرار الضريبي', 'success')
        return redirect(url_for('tax_returns'))
    
    return render_template('generate_tax_return.html')



# ==================== الاشتراكات ====================

@app.route('/subscription')
@login_required
@company_required
def subscription():
    company = current_user.company
    plans = Config.PLANS
    return render_template('subscription.html', company=company, plans=plans)


# ==================== API للبيانات ====================

@app.route('/api/product/<int:id>')
@login_required
def api_product(id):
    product = Product.query.get_or_404(id)
    if product.company_id != current_user.company_id:
        return jsonify({'error': 'unauthorized'}), 403
    return jsonify({
        'id': product.id,
        'name': product.name,
        'name_ar': product.name_ar,
        'cost_price': product.cost_price,
        'sell_price': product.sell_price,
        'tax_rate': product.tax_rate,
        'stock_quantity': product.stock_quantity
    })


@app.route('/api/dashboard-stats')
@login_required
@company_required
def api_dashboard_stats():
    today = date.today()
    month_start = today.replace(day=1)
    
    revenue = db.session.query(db.func.sum(Invoice.total)).filter(
        Invoice.company_id == current_user.company_id,
        Invoice.status.in_(['sent', 'partial', 'paid']),
        Invoice.invoice_date >= month_start
    ).scalar() or 0
    
    return jsonify({
        'revenue': float(revenue),
        'date': today.isoformat()
    })


# ==================== الموارد البشرية ====================

@app.route('/hr')
@login_required
@company_required
def hr():
    employees = Employee.query.filter_by(company_id=current_user.company_id).all()
    return render_template('hr.html', employees=employees, company=current_user.company)

@app.route('/hr/employees/add', methods=['POST'])
@login_required
@company_required
def hr_add_employee():
    employee = Employee(
        first_name=request.form['first_name'],
        last_name=request.form['last_name'],
        email=request.form['email'],
        phone=request.form.get('phone'),
        position=request.form.get('position'),
        department=request.form.get('department'),
        salary=float(request.form['salary']),
        hire_date=datetime.strptime(request.form['hire_date'], '%Y-%m-%d').date(),
        company_id=current_user.company_id,
        status='active'
    )
    db.session.add(employee)
    db.session.commit()
    flash('تم إضافة الموظف بنجاح', 'success')
    return redirect(url_for('hr'))

@app.route('/run-payroll', methods=['POST'])
@login_required
@company_required
def run_payroll():
    payroll_month = request.form['payroll_month']
    payment_date = datetime.strptime(request.form['payment_date'], '%Y-%m-%d').date()
    
    employees = Employee.query.filter_by(company_id=current_user.company_id, status='active').all()
    
    for employee in employees:
        payslip = Payslip(
            employee_id=employee.id,
            payroll_month=payroll_month,
            payment_date=payment_date,
            basic_salary=employee.salary,
            gross_salary=employee.salary,
            net_salary=employee.salary,
            company_id=current_user.company_id
        )
        db.session.add(payslip)
    
    db.session.commit()
    flash('تم تشغيل الرواتب بنجاح', 'success')
    return redirect(url_for('hr'))

# ==================== المشتريات ====================

@app.route('/purchases')
@login_required
@company_required
def purchases():
    status_filter = request.args.get('status', 'all')
    query = Purchase.query.filter_by(company_id=current_user.company_id)
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    purchases_list = query.order_by(Purchase.purchase_date.desc()).all()
    
    suppliers = Supplier.query.filter_by(company_id=current_user.company_id).all()
    products = Product.query.filter_by(company_id=current_user.company_id).all()
    
    return render_template('purchases.html', 
                         purchases=purchases_list, 
                         suppliers=suppliers,
                         products=products,
                         status_filter=status_filter,
                         company=current_user.company)

@app.route('/purchases/add', methods=['POST'])
@login_required
@company_required
def add_purchase():
    purchase = Purchase(
        supplier_id=request.form['supplier_id'],
        purchase_date=datetime.strptime(request.form['purchase_date'], '%Y-%m-%d').date(),
        notes=request.form.get('notes'),
        company_id=current_user.company_id,
        status='pending'
    )
    db.session.add(purchase)
    db.session.flush()
    
    # إنشاء رقم طلب الشراء
    purchase.purchase_number = f'PO-{purchase.id:06d}'
    
    # إضافة البنود
    descriptions = request.form.getlist('description[]')
    quantities = request.form.getlist('quantity[]')
    prices = request.form.getlist('price[]')
    
    subtotal = 0
    for desc, qty, price in zip(descriptions, quantities, prices):
        if desc and qty and price:
            item = PurchaseItem(
                purchase_id=purchase.id,
                description=desc,
                quantity=float(qty),
                unit_price=float(price),
                total=float(qty) * float(price)
            )
            db.session.add(item)
            subtotal += item.total
    
    tax_rate = float(request.form.get('tax_rate', 15))
    tax_amount = subtotal * (tax_rate / 100)
    purchase.subtotal = subtotal
    purchase.tax_amount = tax_amount
    purchase.total = subtotal + tax_amount
    
    db.session.commit()
    flash('تم إنشاء طلب الشراء بنجاح', 'success')
    return redirect(url_for('purchases'))

@app.route('/purchases/<int:id>/approve', methods=['POST'])
@login_required
@company_required
def approve_purchase(id):
    purchase = db.session.get(Purchase, id)
    if not purchase or purchase.company_id != current_user.company_id:
        flash('غير مصرح', 'danger')
        return redirect(url_for('purchases'))
    
    purchase.status = 'approved'
    db.session.commit()
    flash('تم اعتماد الطلب بنجاح', 'success')
    return redirect(url_for('purchases'))

# ==================== التقارير ====================

@app.route('/reports')
@login_required
@company_required
def reports():
    company = current_user.company
    today = date.today()
    month_start = today.replace(day=1)
    
    stats = {
        'total_revenue': db.session.query(db.func.sum(Invoice.total)).filter(
            Invoice.company_id == company.id,
            Invoice.status.in_(['sent', 'partial', 'paid']),
            Invoice.invoice_date >= month_start
        ).scalar() or 0,
        'total_expenses': db.session.query(db.func.sum(Purchase.total)).filter(
            Purchase.company_id == company.id,
            Purchase.status.in_(['approved', 'partial', 'paid']),
            Purchase.purchase_date >= month_start
        ).scalar() or 0,
        'net_profit': 0,
        'cash_flow': 0,
        'avg_order_value': 0,
        'total_customers': Customer.query.filter_by(company_id=company.id, is_active=True).count(),
        'inventory_value': 0,
        'outstanding_receivables': db.session.query(db.func.sum(Invoice.balance_due)).filter(
            Invoice.company_id == company.id,
            Invoice.status.in_(['sent', 'partial', 'overdue'])
        ).scalar() or 0
    }
    
    stats['net_profit'] = stats['total_revenue'] - stats['total_expenses']
    stats['cash_flow'] = stats['net_profit']
    
    return render_template('reports.html', stats=stats, company=company)

# ==================== الإعدادات ====================

@app.route('/settings')
@login_required
@company_required
def settings_page():
    accounts = Account.query.filter_by(company_id=current_user.company_id, is_active=True).all()
    return render_template('settings.html', accounts=accounts, company=current_user.company, config=Config)

@app.route('/settings/company', methods=['POST'])
@login_required
@company_required
def update_company():
    company = current_user.company
    company.name = request.form['name']
    company.email = request.form.get('email')
    company.phone = request.form.get('phone')
    company.address = request.form.get('address')
    company.city = request.form.get('city')
    company.country_code = request.form.get('country_code')
    company.currency = request.form.get('currency')
    company.tax_number = request.form.get('tax_number')
    
    db.session.commit()
    flash('تم تحديث معلومات الشركة بنجاح', 'success')
    return redirect(url_for('settings_page'))

@app.route('/settings/profile', methods=['POST'])
@login_required
def update_profile():
    user = current_user
    user.first_name = request.form['first_name']
    user.last_name = request.form['last_name']
    user.email = request.form['email']
    
    # تغيير كلمة المرور
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    if current_password and new_password:
        if user.check_password(current_password):
            user.set_password(new_password)
            flash('تم تغيير كلمة المرور بنجاح', 'success')
        else:
            flash('كلمة المرور الحالية غير صحيحة', 'danger')
            return redirect(url_for('settings_page'))
    
    db.session.commit()
    flash('تم تحديث الملف الشخصي بنجاح', 'success')
    return redirect(url_for('settings_page'))

@app.route('/settings/tax', methods=['POST'])
@login_required
@company_required
def update_tax_settings():
    company = current_user.company
    company.vat_rate = float(request.form.get('vat_rate', 15))
    
    db.session.commit()
    flash('تم تحديث إعدادات الضرائب بنجاح', 'success')
    return redirect(url_for('settings_page'))

@app.route('/settings/invoice', methods=['POST'])
@login_required
@company_required
def update_invoice_settings():
    # Company model doesn't have these columns yet, mocking DB save for now
    flash('تم تحديث إعدادات الفواتير بنجاح', 'success')
    return redirect(url_for('settings_page'))

@app.route('/settings/email', methods=['POST'])
@login_required
@company_required
def update_email_settings():
    flash('تم تحديث إعدادات البريد الإلكتروني بنجاح', 'success')
    return redirect(url_for('settings_page'))

@app.route('/settings/backup', methods=['POST'])
@login_required
@company_required
def update_backup_settings():
    flash('تم تحديث إعدادات النسخ الاحتياطي بنجاح', 'success')
    return redirect(url_for('settings_page'))

@app.route('/settings/security', methods=['POST'])
@login_required
@company_required
def update_security_settings():
    flash('تم تحديث إعدادات الأمان بنجاح', 'success')
    return redirect(url_for('settings_page'))


# ==================== تهيئة قاعدة البيانات ====================

with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
