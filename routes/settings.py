import json
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import ResearchProfile

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

PLATFORM_OPTIONS = [
    ('arxiv', 'arXiv'),
    ('semantic_scholar', 'Semantic Scholar'),
    ('pubmed', 'PubMed'),
    ('crossref', 'CrossRef'),
]

BLOG_OPTIONS = [
    ('openai_blog', 'OpenAI Research Blog'),
    ('google_ai', 'Google AI Blog'),
    ('deepmind', 'DeepMind Blog'),
    ('anthropic', 'Anthropic Blog'),
    ('microsoft_research', 'Microsoft Research Blog'),
    ('sebastian_ruder', "Sebastian Ruder's Blog"),
    ('distill', 'Distill.pub'),
    ('towards_data_science', 'Towards Data Science'),
]


@settings_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def research_profile():
    profile = current_user.profile
    if not profile:
        profile = ResearchProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()

    if request.method == 'POST':
        profile.main_topic = request.form.get('main_topic', '').strip()
        profile.keywords = request.form.get('keywords', '').strip()
        profile.must_include = request.form.get('must_include', '').strip()
        profile.exclude_terms = request.form.get('exclude_terms', '').strip()
        profile.focus_areas = request.form.get('focus_areas', '').strip()

        selected_platforms = request.form.getlist('platforms')
        if not selected_platforms:
            selected_platforms = ['arxiv']
        profile.set_platforms(selected_platforms)

        try:
            apd = int(request.form.get('articles_per_day', 5))
            profile.articles_per_day = max(1, min(20, apd))
        except:
            profile.articles_per_day = 5

        profile.include_blogs = 'include_blogs' in request.form
        selected_blogs = request.form.getlist('blogs')
        profile.set_selected_blogs(selected_blogs)

        openai_key = request.form.get('openai_api_key', '').strip()
        if openai_key:
            current_user.openai_api_key = openai_key

        db.session.commit()
        flash('Research profile updated successfully.', 'success')
        return redirect(url_for('dashboard.home'))

    return render_template('settings.html', profile=profile,
                           platform_options=PLATFORM_OPTIONS, blog_options=BLOG_OPTIONS)


@settings_bp.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        openai_key = request.form.get('openai_api_key', '').strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if name:
            current_user.name = name
        if openai_key:
            current_user.openai_api_key = openai_key

        if current_password and new_password:
            if not current_user.check_password(current_password):
                flash('Current password is incorrect.', 'error')
                return render_template('account.html')
            if new_password != confirm_password:
                flash('New passwords do not match.', 'error')
                return render_template('account.html')
            if len(new_password) < 8:
                flash('Password must be at least 8 characters.', 'error')
                return render_template('account.html')
            current_user.set_password(new_password)

        db.session.commit()
        flash('Account updated successfully.', 'success')

    return render_template('account.html')
