from app import app, db, User, Company
from datetime import datetime, timedelta

def create_admin():
    with app.app_context():
        # Check if admin already exists
        if User.query.filter_by(email='admin@company.com').first():
            print('Admin user already exists!')
            return
        
        # Create company
        company = Company(
            name='شركة تجريبية',
            name_ar='شركة تجريبية',
            country_code='SA',
            currency='SAR',
            subscription_plan='professional',
            subscription_status='active',
            subscription_start=datetime.utcnow(),
            subscription_end=datetime.utcnow() + timedelta(days=365)
        )
        db.session.add(company)
        db.session.flush()
        
        # Create admin user
        admin = User(
            email='admin@company.com',
            first_name='أدمن',
            last_name='النظام',
            role='admin',
            company_id=company.id
        )
        admin.set_password('admin123')
        db.session.add(admin)
        
        db.session.commit()
        print('Admin user created successfully!')
        print('Email: admin@company.com')
        print('Password: admin123')

if __name__ == '__main__':
    create_admin()
