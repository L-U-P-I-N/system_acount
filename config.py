import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///accounting.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Stripe
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY', '')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Subscription Plans
    PLANS = {
        'basic': {
            'name': 'Basic',
            'name_ar': 'أساسي',
            'price_usd': 29.99,
            'price_sar': 112.00,
            'max_users': 3,
            'max_invoices': 100,
            'features': ['accounting', 'invoicing', 'reports']
        },
        'professional': {
            'name': 'Professional',
            'name_ar': 'احترافي',
            'price_usd': 79.99,
            'price_sar': 300.00,
            'max_users': 10,
            'max_invoices': 1000,
            'features': ['accounting', 'invoicing', 'reports', 'payroll', 'tax', 'inventory']
        },
        'enterprise': {
            'name': 'Enterprise',
            'name_ar': 'مؤسسات',
            'price_usd': 199.99,
            'price_sar': 750.00,
            'max_users': -1,
            'max_invoices': -1,
            'features': ['all']
        }
    }

    # Tax Configurations
    TAX_CONFIGS = {
        'SA': {
            'name': 'Saudi Arabia',
            'name_ar': 'المملكة العربية السعودية',
            'currency': 'SAR',
            'vat_rate': 15.0,
            'tax_number_label': 'الرقم الضريبي',
            'tax_number_format': r'^\d{15}$',
            'fiscal_year_start': '01-01',
            'zatca_enabled': True
        },
        'AE': {
            'name': 'UAE',
            'name_ar': 'الإمارات العربية المتحدة',
            'currency': 'AED',
            'vat_rate': 5.0,
            'tax_number_label': 'TRN',
            'tax_number_format': r'^\d{15}$',
            'fiscal_year_start': '01-01',
            'zatca_enabled': False
        },
        'US': {
            'name': 'United States',
            'name_ar': 'الولايات المتحدة',
            'currency': 'USD',
            'vat_rate': 0.0,
            'sales_tax': True,
            'tax_number_label': 'EIN',
            'tax_number_format': r'^\d{2}-\d{7}$',
            'fiscal_year_start': '01-01',
            'zatca_enabled': False
        },
        'EG': {
            'name': 'Egypt',
            'name_ar': 'مصر',
            'currency': 'EGP',
            'vat_rate': 14.0,
            'tax_number_label': 'الرقم الضريبي',
            'fiscal_year_start': '01-01',
            'zatca_enabled': False
        },
        'JO': {
            'name': 'Jordan',
            'name_ar': 'الأردن',
            'currency': 'JOD',
            'vat_rate': 16.0,
            'tax_number_label': 'الرقم الضريبي',
            'fiscal_year_start': '01-01',
            'zatca_enabled': False
        }
    }