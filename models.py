from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from decimal import Decimal
import json

db = SQLAlchemy()

# ==================== المستخدمين والشركات ====================

class Company(db.Model):
    __tablename__ = 'companies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country_code = db.Column(db.String(5), default='SA')
    currency = db.Column(db.String(5), default='SAR')
    tax_number = db.Column(db.String(50))
    commercial_reg = db.Column(db.String(50))
    logo_url = db.Column(db.String(500))
    fiscal_year_start = db.Column(db.String(5), default='01-01')
    
    # Subscription
    subscription_plan = db.Column(db.String(20), default='basic')
    subscription_status = db.Column(db.String(20), default='trial')  # trial, active, expired, cancelled
    subscription_start = db.Column(db.DateTime)
    subscription_end = db.Column(db.DateTime)
    stripe_customer_id = db.Column(db.String(100))
    stripe_subscription_id = db.Column(db.String(100))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', backref='company', lazy='dynamic')
    accounts = db.relationship('Account', backref='company', lazy='dynamic')
    journals = db.relationship('JournalEntry', backref='company', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='company', lazy='dynamic')
    purchases = db.relationship('Purchase', backref='company', lazy='dynamic')
    customers = db.relationship('Customer', backref='company', lazy='dynamic')
    suppliers = db.relationship('Supplier', backref='company', lazy='dynamic')
    employees = db.relationship('Employee', backref='company', lazy='dynamic')
    products = db.relationship('Product', backref='company', lazy='dynamic')
    tax_settings = db.relationship('TaxSetting', backref='company', lazy='dynamic')


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(20), default='user')  # admin, accountant, user, viewer
    language = db.Column(db.String(5), default='ar')
    is_active = db.Column(db.Boolean, default=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


# ==================== شجرة الحسابات ====================

class Account(db.Model):
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200))
    account_type = db.Column(db.String(30), nullable=False)
    # asset, liability, equity, revenue, expense, cogs
    parent_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    is_active = db.Column(db.Boolean, default=True)
    is_system = db.Column(db.Boolean, default=False)  # حسابات النظام لا تحذف
    description = db.Column(db.Text)
    balance = db.Column(db.Float, default=0.0)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Self-referential relationship
    children = db.relationship('Account', backref=db.backref('parent', remote_side=[id]))
    journal_lines = db.relationship('JournalLine', backref='account', lazy='dynamic')


# ==================== القيود المحاسبية ====================

class JournalEntry(db.Model):
    __tablename__ = 'journal_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    entry_number = db.Column(db.String(20), nullable=False)
    entry_date = db.Column(db.Date, nullable=False, default=date.today)
    description = db.Column(db.Text)
    reference = db.Column(db.String(100))
    entry_type = db.Column(db.String(20), default='manual')
    # manual, invoice, purchase, payroll, adjustment
    status = db.Column(db.String(20), default='draft')  # draft, posted, reversed
    total_debit = db.Column(db.Float, default=0.0)
    total_credit = db.Column(db.Float, default=0.0)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    posted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    posted_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    lines = db.relationship('JournalLine', backref='journal_entry', 
                           cascade='all, delete-orphan', lazy='dynamic')
    
    creator = db.relationship('User', foreign_keys=[created_by])
    poster = db.relationship('User', foreign_keys=[posted_by])


class JournalLine(db.Model):
    __tablename__ = 'journal_lines'
    
    id = db.Column(db.Integer, primary_key=True)
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    description = db.Column(db.String(300))
    debit = db.Column(db.Float, default=0.0)
    credit = db.Column(db.Float, default=0.0)
    cost_center = db.Column(db.String(50))


# ==================== العملاء والموردين ====================

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20))
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    mobile = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    tax_number = db.Column(db.String(50))
    credit_limit = db.Column(db.Float, default=0.0)
    balance = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    invoices = db.relationship('Invoice', backref='customer', lazy='dynamic')


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20))
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    tax_number = db.Column(db.String(50))
    balance = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    purchases = db.relationship('Purchase', backref='supplier', lazy='dynamic')


# ==================== المنتجات ====================

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50))
    name = db.Column(db.String(200), nullable=False)
    name_ar = db.Column(db.String(200))
    description = db.Column(db.Text)
    product_type = db.Column(db.String(20), default='product')  # product, service
    unit = db.Column(db.String(20), default='unit')
    cost_price = db.Column(db.Float, default=0.0)
    sell_price = db.Column(db.Float, default=0.0)
    tax_rate = db.Column(db.Float, default=0.0)
    is_taxable = db.Column(db.Boolean, default=True)
    stock_quantity = db.Column(db.Float, default=0.0)
    min_stock = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    income_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    expense_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== الفواتير (المبيعات) ====================

class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(30), nullable=False)
    invoice_date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    status = db.Column(db.String(20), default='draft')
    # draft, sent, partial, paid, overdue, cancelled
    subtotal = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    discount_type = db.Column(db.String(10), default='amount')  # amount, percent
    tax_amount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)
    balance_due = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(5), default='SAR')
    notes = db.Column(db.Text)
    terms = db.Column(db.Text)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    items = db.relationship('InvoiceItem', backref='invoice', 
                           cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='invoice', lazy='dynamic')
    creator = db.relationship('User', foreign_keys=[created_by])


class InvoiceItem(db.Model):
    __tablename__ = 'invoice_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    description = db.Column(db.String(300), nullable=False)
    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    tax_rate = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    
    product = db.relationship('Product')


# ==================== المشتريات ====================

class Purchase(db.Model):
    __tablename__ = 'purchases'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_number = db.Column(db.String(30), nullable=False)
    purchase_date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    status = db.Column(db.String(20), default='draft')
    subtotal = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    paid_amount = db.Column(db.Float, default=0.0)
    balance_due = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(5), default='SAR')
    notes = db.Column(db.Text)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    items = db.relationship('PurchaseItem', backref='purchase', 
                           cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])


class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    description = db.Column(db.String(300), nullable=False)
    quantity = db.Column(db.Float, default=1.0)
    unit_price = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    tax_rate = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    total = db.Column(db.Float, default=0.0)
    
    product = db.relationship('Product')


# ==================== المدفوعات ====================

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(30), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    payment_type = db.Column(db.String(20))  # received, made
    payment_method = db.Column(db.String(20))  # cash, bank, check, card
    amount = db.Column(db.Float, nullable=False)
    reference = db.Column(db.String(100))
    notes = db.Column(db.Text)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'))
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== الرواتب ====================

class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_number = db.Column(db.String(20))
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    first_name_ar = db.Column(db.String(50))
    last_name_ar = db.Column(db.String(50))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    national_id = db.Column(db.String(20))
    passport_number = db.Column(db.String(20))
    nationality = db.Column(db.String(50))
    gender = db.Column(db.String(10))
    date_of_birth = db.Column(db.Date)
    hire_date = db.Column(db.Date, nullable=False)
    termination_date = db.Column(db.Date)
    department = db.Column(db.String(100))
    position = db.Column(db.String(100))
    employment_type = db.Column(db.String(20), default='full_time')
    # full_time, part_time, contract
    
    # Salary Details
    basic_salary = db.Column(db.Float, default=0.0)
    housing_allowance = db.Column(db.Float, default=0.0)
    transport_allowance = db.Column(db.Float, default=0.0)
    food_allowance = db.Column(db.Float, default=0.0)
    phone_allowance = db.Column(db.Float, default=0.0)
    other_allowances = db.Column(db.Float, default=0.0)
    
    # Insurance & Deductions
    gosi_employee_pct = db.Column(db.Float, default=9.75)  # نسبة التأمينات للموظف
    gosi_company_pct = db.Column(db.Float, default=11.75)  # نسبة التأمينات للشركة
    medical_insurance = db.Column(db.Float, default=0.0)
    
    # Bank
    bank_name = db.Column(db.String(100))
    bank_account = db.Column(db.String(30))
    iban = db.Column(db.String(34))
    
    status = db.Column(db.String(20), default='active')  # active, inactive, terminated
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    payslips = db.relationship('Payslip', backref='employee', lazy='dynamic')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def full_name_ar(self):
        if self.first_name_ar:
            return f"{self.first_name_ar} {self.last_name_ar or ''}"
        return self.full_name
    
    @property
    def gross_salary(self):
        return (self.basic_salary + self.housing_allowance + 
                self.transport_allowance + self.food_allowance + 
                self.phone_allowance + self.other_allowances)


class Payslip(db.Model):
    __tablename__ = 'payslips'
    
    id = db.Column(db.Integer, primary_key=True)
    payslip_number = db.Column(db.String(30), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    
    # Earnings
    basic_salary = db.Column(db.Float, default=0.0)
    housing_allowance = db.Column(db.Float, default=0.0)
    transport_allowance = db.Column(db.Float, default=0.0)
    food_allowance = db.Column(db.Float, default=0.0)
    phone_allowance = db.Column(db.Float, default=0.0)
    other_allowances = db.Column(db.Float, default=0.0)
    overtime_amount = db.Column(db.Float, default=0.0)
    commission = db.Column(db.Float, default=0.0)
    bonus = db.Column(db.Float, default=0.0)
    gross_salary = db.Column(db.Float, default=0.0)
    
    # Deductions
    gosi_employee = db.Column(db.Float, default=0.0)
    gosi_company = db.Column(db.Float, default=0.0)
    income_tax = db.Column(db.Float, default=0.0)
    medical_insurance = db.Column(db.Float, default=0.0)
    loan_deduction = db.Column(db.Float, default=0.0)
    absence_deduction = db.Column(db.Float, default=0.0)
    other_deductions = db.Column(db.Float, default=0.0)
    total_deductions = db.Column(db.Float, default=0.0)
    
    net_salary = db.Column(db.Float, default=0.0)
    
    status = db.Column(db.String(20), default='draft')  # draft, approved, paid
    payment_date = db.Column(db.Date)
    payment_method = db.Column(db.String(20))
    
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    journal_entry_id = db.Column(db.Integer, db.ForeignKey('journal_entries.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PayrollRun(db.Model):
    __tablename__ = 'payroll_runs'
    
    id = db.Column(db.Integer, primary_key=True)
    run_number = db.Column(db.String(30), nullable=False)
    period_month = db.Column(db.Integer, nullable=False)
    period_year = db.Column(db.Integer, nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    total_gross = db.Column(db.Float, default=0.0)
    total_deductions = db.Column(db.Float, default=0.0)
    total_net = db.Column(db.Float, default=0.0)
    total_gosi_company = db.Column(db.Float, default=0.0)
    employee_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='draft')
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== الضرائب ====================

class TaxSetting(db.Model):
    __tablename__ = 'tax_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    tax_name = db.Column(db.String(100), nullable=False)
    tax_name_ar = db.Column(db.String(100))
    tax_type = db.Column(db.String(20))  # vat, sales_tax, income_tax, withholding
    rate = db.Column(db.Float, default=0.0)
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))


class TaxReturn(db.Model):
    __tablename__ = 'tax_returns'
    
    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(30))
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    tax_type = db.Column(db.String(20))  # vat, income_tax
    
    # VAT Details
    total_sales = db.Column(db.Float, default=0.0)
    total_sales_tax = db.Column(db.Float, default=0.0)
    total_purchases = db.Column(db.Float, default=0.0)
    total_purchases_tax = db.Column(db.Float, default=0.0)
    tax_due = db.Column(db.Float, default=0.0)
    tax_refund = db.Column(db.Float, default=0.0)
    net_tax = db.Column(db.Float, default=0.0)
    
    # Adjustments
    adjustments = db.Column(db.Float, default=0.0)
    penalties = db.Column(db.Float, default=0.0)
    
    status = db.Column(db.String(20), default='draft')  # draft, filed, paid
    filing_date = db.Column(db.Date)
    payment_date = db.Column(db.Date)
    
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== سجل العمليات ====================

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50))  # create, update, delete, login, logout
    entity_type = db.Column(db.String(50))  # invoice, payment, journal, etc
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User')