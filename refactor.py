import os
import re

files_to_process = [
    "suppliers.html",
    "products.html",
    "journal_entry_form.html",
    "journal_entries.html",
    "invoice_view.html",
    "invoice_form.html",
    "invoices.html",
    "customers.html",
    "chart_of_accounts.html"
]

base_dir = r"D:\خال\مجلد جديد (2) (1)\مجلد جديد (2)\templates"

for filename in files_to_process:
    filepath = os.path.join(base_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Extract title
    title_match = re.search(r'<title>(.*?)</title>', content)
    title = title_match.group(1).replace(' - {{ company.name }}', '').strip() if title_match else filename

    # 2. Extract specific styles (exclude generic ones)
    style_match = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
    styles = ""
    if style_match:
        all_styles = style_match.group(1)
        # Remove body, sidebar, and main-content styles as base.html handles them
        clean_styles = re.sub(r'body\s*\{[^}]+\}', '', all_styles)
        clean_styles = re.sub(r'\.sidebar\s*(?:[^{]+)?\{[^}]+\}', '', clean_styles)
        clean_styles = re.sub(r'\.main-content\s*\{[^}]+\}', '', clean_styles)
        styles = clean_styles.strip()

    # 3. Extract main content (everything inside col-md-10 main-content up to the scripts or end of body)
    # The structure usually has:
    # <div class="col-md-10 main-content"> ... </div>
    # </div></div>
    # modals
    # scripts
    
    # We will slice from <div class="col-md-10 main-content"> to </body>
    main_start = content.find('<div class="col-md-10 main-content">')
    if main_start == -1:
        print(f"Skipping {filename}, no main-content found.")
        continue
        
    # We need to skip the wrapper <div class="col-md-10 main-content">
    start_idx = content.find('>', main_start) + 1
    end_idx = content.rfind('</body>')
    
    body_content = content[start_idx:end_idx].strip()
    
    # Body content currently ends with </div> (to close col-md-10), </div> (for row), </div> (for container-fluid)
    # Let's remove those three closing divs
    # We'll just remove the last 3 '</div>' before the scripts/modals if they are at the end, but they might be before modals.
    # Actually, a better way: The main content ends where the row ends.
    # Let's use regex to find the end of the col-md-10 div. Since regex can't count nested divs perfectly, 
    # we can just take everything and remove the extra closing divs of the wrapper.
    # The wrapper is: <div class="container-fluid"><div class="row"><div class="col-md-2..."></div><div class="col-md-10...">
    
    wrapper_endings = re.search(r'</div>\s*</div>\s*</div>\s*(<!--.*?Modal.*)', body_content, re.DOTALL)
    if wrapper_endings:
        body_content = body_content[:wrapper_endings.start()] + wrapper_endings.group(1)
    else:
        # If no modal, just remove the last 3 </div>
        body_content = re.sub(r'</div>\s*</div>\s*</div>\s*$', '', body_content)
    
    # 4. Extract any scripts (excluding the bootstrap bundle which base.html has)
    scripts = ""
    # find all script tags
    script_tags = re.findall(r'(<script.*?>.*?</script>)', content, re.DOTALL)
    for script in script_tags:
        if 'bootstrap.bundle.min.js' not in script:
            scripts += script + '\n'
            # remove from body_content if present
            body_content = body_content.replace(script, '')

    # Assemble new template
    new_template = f"{{% extends \"base.html\" %}}\n\n"
    new_template += f"{{% block title %}}{title}{{% endblock %}}\n\n"
    
    if styles:
        new_template += f"{{% block extra_css %}}\n<style>\n{styles}\n</style>\n{{% endblock %}}\n\n"
        
    new_template += f"{{% block content %}}\n"
    new_template += body_content.strip() + "\n"
    new_template += f"{{% endblock %}}\n"
    
    if scripts:
        new_template += f"\n{{% block extra_js %}}\n{scripts.strip()}\n{{% endblock %}}\n"
        
    # Overwrite the file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_template)
        
    print(f"Refactored {filename}")
