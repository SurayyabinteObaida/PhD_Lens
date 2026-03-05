import os
import json
import time
import feedparser
import requests
from datetime import datetime, timedelta
from openai import OpenAI
from bs4 import BeautifulSoup


BLOG_FEEDS = {
    'openai_blog': {
        'name': 'OpenAI Research Blog',
        'url': 'https://openai.com/blog/rss.xml',
        'fallback': 'https://openai.com/research'
    },
    'google_ai': {
        'name': 'Google AI Blog',
        'url': 'https://blog.research.google/feeds/posts/default',
        'fallback': None
    },
    'deepmind': {
        'name': 'DeepMind Blog',
        'url': 'https://deepmind.google/blog/rss.xml',
        'fallback': None
    },
    'anthropic': {
        'name': 'Anthropic Blog',
        'url': 'https://www.anthropic.com/research',
        'fallback': None
    },
    'microsoft_research': {
        'name': 'Microsoft Research Blog',
        'url': 'https://www.microsoft.com/en-us/research/feed/',
        'fallback': None
    },
    'sebastian_ruder': {
        'name': "Sebastian Ruder's Blog",
        'url': 'https://ruder.io/rss',
        'fallback': None
    },
    'distill': {
        'name': 'Distill.pub',
        'url': 'https://distill.pub/rss.xml',
        'fallback': None
    },
    'towards_data_science': {
        'name': 'Towards Data Science',
        'url': 'https://towardsdatascience.com/feed',
        'fallback': None
    },
}


def build_search_query(profile):
    """Build an effective boolean search query from the research profile.
    Avoids exact full-topic phrase matching which fails on novel/specific topics.
    Instead uses OR across topic words and keywords for broad recall,
    then lets the AI filter by relevance score.
    """
    topic_terms = []
    if profile.main_topic:
        # Split topic into meaningful words (skip stop words)
        stop = {'in', 'of', 'the', 'a', 'an', 'for', 'and', 'or', 'on', 'at', 'to', 'with'}
        words = [w.strip() for w in profile.main_topic.split() if w.lower() not in stop and len(w) > 2]
        topic_terms.extend(words[:5])

    kw_terms = []
    if profile.keywords:
        kws = [k.strip() for k in profile.keywords.split(',') if k.strip()][:4]
        kw_terms.extend(kws)

    must_terms = []
    if profile.must_include:
        must_terms = [m.strip() for m in profile.must_include.split(',') if m.strip()][:2]

    # Combine topic words and keywords into one OR block for broad recall
    all_terms = topic_terms + kw_terms
    if not all_terms:
        return profile.main_topic or ''

    query = '(' + ' OR '.join(f'"{t}"' for t in all_terms) + ')'

    # AND in must_include terms for precision
    for m in must_terms:
        query += ' AND "' + m + '"'

    return query


def fetch_arxiv_articles(query, max_results=10, exclude_terms=None):
    """Fetch from arXiv API"""
    articles = []
    try:
        base_url = 'https://export.arxiv.org/api/query'
        params = {
            'search_query': f'all:{query} AND (cat:cs.CR OR cat:cs.AI OR cat:cs.SE OR cat:cs.LG OR cat:cs.CL)',
            'start': 0,
            'max_results': max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }
        resp = requests.get(base_url, params=params, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)

        for entry in feed.entries:
            title = entry.get('title', '').replace('\n', ' ').strip()
            abstract = entry.get('summary', '').replace('\n', ' ').strip()

            if exclude_terms:
                excl = [e.strip().lower() for e in exclude_terms.split(',') if e.strip()]
                text_lower = (title + ' ' + abstract).lower()
                if any(ex in text_lower for ex in excl):
                    continue

            authors = ', '.join([a.get('name', '') for a in entry.get('authors', [])[:4]])
            url = entry.get('link', '')
            published = entry.get('published', '')[:10]

            articles.append({
                'title': title,
                'authors': authors,
                'abstract': abstract[:1500],
                'url': url,
                'source_platform': 'arXiv',
                'published_date': published,
                'is_blog_post': False
            })
    except Exception as e:
        print(f"arXiv fetch error: {e}")
    return articles


def fetch_semantic_scholar_articles(query, max_results=10, exclude_terms=None):
    """Fetch from Semantic Scholar API"""
    articles = []
    try:
        base_url = 'https://api.semanticscholar.org/graph/v1/paper/search'
        params = {
            'query': query,
            'limit': max_results,
            'fields': 'title,authors,abstract,url,year,publicationDate,externalIds',
            'sort': 'publicationDate:desc'
        }
        headers = {'User-Agent': 'PhDLens/1.0 (research tool)'}
        resp = requests.get(base_url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for paper in data.get('data', []):
            title = paper.get('title', '')
            abstract = paper.get('abstract', '') or ''

            if exclude_terms:
                excl = [e.strip().lower() for e in exclude_terms.split(',') if e.strip()]
                text_lower = (title + ' ' + abstract).lower()
                if any(ex in text_lower for ex in excl):
                    continue

            authors_list = paper.get('authors', [])
            authors = ', '.join([a.get('name', '') for a in authors_list[:4]])
            url = paper.get('url', '')
            if not url:
                ext_ids = paper.get('externalIds', {})
                if ext_ids.get('ArXiv'):
                    url = f"https://arxiv.org/abs/{ext_ids['ArXiv']}"
                elif ext_ids.get('DOI'):
                    url = f"https://doi.org/{ext_ids['DOI']}"

            pub_date = paper.get('publicationDate', '') or str(paper.get('year', ''))

            articles.append({
                'title': title,
                'authors': authors,
                'abstract': abstract[:1500],
                'url': url,
                'source_platform': 'Semantic Scholar',
                'published_date': pub_date,
                'is_blog_post': False
            })
    except Exception as e:
        print(f"Semantic Scholar fetch error: {e}")
    return articles


def fetch_pubmed_articles(query, max_results=10, exclude_terms=None):
    """Fetch from PubMed E-utilities"""
    articles = []
    try:
        search_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'retmode': 'json',
            'sort': 'pub_date'
        }
        resp = requests.get(search_url, params=params, timeout=15)
        resp.raise_for_status()
        ids = resp.json().get('esearchresult', {}).get('idlist', [])
        if not ids:
            return articles

        fetch_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
        fetch_params = {
            'db': 'pubmed',
            'id': ','.join(ids[:max_results]),
            'retmode': 'xml',
            'rettype': 'abstract'
        }
        fetch_resp = requests.get(fetch_url, params=fetch_params, timeout=15)
        soup = BeautifulSoup(fetch_resp.text, 'xml')

        for article_tag in soup.find_all('PubmedArticle')[:max_results]:
            title_tag = article_tag.find('ArticleTitle')
            abstract_tag = article_tag.find('AbstractText')
            title = title_tag.get_text() if title_tag else ''
            abstract = abstract_tag.get_text() if abstract_tag else ''

            if exclude_terms:
                excl = [e.strip().lower() for e in exclude_terms.split(',') if e.strip()]
                text_lower = (title + ' ' + abstract).lower()
                if any(ex in text_lower for ex in excl):
                    continue

            pmid_tag = article_tag.find('PMID')
            pmid = pmid_tag.get_text() if pmid_tag else ''
            url = f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/' if pmid else ''

            authors = []
            for author in article_tag.find_all('Author')[:4]:
                ln = author.find('LastName')
                fn = author.find('ForeName')
                if ln:
                    authors.append(f"{ln.get_text()}{', ' + fn.get_text() if fn else ''}")

            pub_year_tag = article_tag.find('PubDate')
            pub_year = ''
            if pub_year_tag:
                year_tag = pub_year_tag.find('Year')
                pub_year = year_tag.get_text() if year_tag else ''

            articles.append({
                'title': title,
                'authors': ', '.join(authors),
                'abstract': abstract[:1500],
                'url': url,
                'source_platform': 'PubMed',
                'published_date': pub_year,
                'is_blog_post': False
            })
    except Exception as e:
        print(f"PubMed fetch error: {e}")
    return articles


def fetch_crossref_articles(query, max_results=10, exclude_terms=None):
    """Fetch from CrossRef API"""
    articles = []
    try:
        url = 'https://api.crossref.org/works'
        params = {
            'query': query,
            'rows': max_results,
            'sort': 'published',
            'order': 'desc',
            'select': 'title,author,abstract,URL,published,container-title'
        }
        headers = {'User-Agent': 'PhDLens/1.0 (mailto:user@phdlens.app)'}
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        items = resp.json().get('message', {}).get('items', [])

        for item in items[:max_results]:
            title_list = item.get('title', [])
            title = title_list[0] if title_list else ''
            abstract = item.get('abstract', '') or ''
            abstract = BeautifulSoup(abstract, 'html.parser').get_text()[:1500]

            if exclude_terms:
                excl = [e.strip().lower() for e in exclude_terms.split(',') if e.strip()]
                text_lower = (title + ' ' + abstract).lower()
                if any(ex in text_lower for ex in excl):
                    continue

            authors_list = item.get('author', [])
            authors = ', '.join([
                f"{a.get('family', '')}{', ' + a.get('given', '') if a.get('given') else ''}"
                for a in authors_list[:4]
            ])

            pub = item.get('published', {})
            date_parts = pub.get('date-parts', [[]])[0]
            pub_date = '-'.join(str(p) for p in date_parts) if date_parts else ''

            articles.append({
                'title': title,
                'authors': authors,
                'abstract': abstract,
                'url': item.get('URL', ''),
                'source_platform': 'CrossRef',
                'published_date': pub_date,
                'is_blog_post': False
            })
    except Exception as e:
        print(f"CrossRef fetch error: {e}")
    return articles


def fetch_blog_posts(selected_blogs, query):
    """Fetch from research blogs via RSS"""
    posts = []
    for blog_key in selected_blogs:
        if blog_key not in BLOG_FEEDS:
            continue
        blog_info = BLOG_FEEDS[blog_key]
        try:
            feed = feedparser.parse(blog_info['url'])
            for entry in feed.entries[:3]:
                title = entry.get('title', '')
                summary = entry.get('summary', '') or entry.get('description', '')
                summary = BeautifulSoup(summary, 'html.parser').get_text()[:1500]
                url = entry.get('link', '')
                published = entry.get('published', '')[:10] if entry.get('published') else ''

                posts.append({
                    'title': title,
                    'authors': blog_info['name'],
                    'abstract': summary,
                    'url': url,
                    'source_platform': blog_info['name'],
                    'published_date': published,
                    'is_blog_post': True
                })
        except Exception as e:
            print(f"Blog fetch error ({blog_key}): {e}")
    return posts


def analyze_article_with_ai(client, article_data, profile):
    """Use OpenAI to generate structured insights for an article"""
    system_prompt = """You are an expert academic research analyst helping a PhD student stay current with research literature.
Your task is to analyze research articles and blog posts, extracting structured insights that are immediately useful for literature review and thesis writing.
Always be precise, technical, and academically rigorous. Avoid filler language."""

    user_prompt = f"""Analyze this research article/post for a PhD student researching: {profile.main_topic}
Focus areas: {profile.focus_areas or 'general relevance to topic'}
Keywords of interest: {profile.keywords}

Article Title: {article_data['title']}
Authors: {article_data['authors']}
Abstract/Content: {article_data['abstract']}
Source: {article_data['source_platform']}

Generate a structured analysis in JSON format with these exact keys:
{{
  "highlights": "2-3 sentences on the novelty and main contributions of this work",
  "methodology": "1-2 sentences describing the core methodology or approach",
  "datasets": "Datasets used (write 'Not specified' if not mentioned)",
  "models": "Models or algorithms employed (write 'Not applicable' if blog post)",
  "results": "Key quantitative or qualitative results in 1-2 sentences",
  "soul": "A precise 3-line description that completely captures the essence of this work — what problem, how solved, why it matters",
  "approach_steps": "Key steps in their approach as a numbered list (3-6 steps)",
  "detailed_methodology": "A comprehensive paragraph on the methodology suitable for a literature review",
  "detailed_results": "Detailed results and findings with specific numbers where available",
  "figures_to_review": "Description of figures or visual elements worth examining (if blog post, describe key diagrams)",
  "writeup_summary": "A 150-200 word paragraph ready to be used in a literature review write-up, written in academic third-person style",
  "relevance_score": 0.0
}}

For relevance_score: rate 0.0-1.0 how relevant this article is to the research topic '{profile.main_topic}' with focus on '{profile.focus_areas or profile.keywords}'.

Return only valid JSON."""

    try:
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        text = response.choices[0].message.content.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f"AI analysis error: {e}")
        return None



def _str(val):
    """Ensure AI-returned value is always a plain string, never a list."""
    if isinstance(val, list):
        return '\n'.join(str(i) for i in val)
    return str(val) if val else ''


def run_digest(user, digest):
    """Main function to fetch and analyze articles for a digest"""
    from extensions import db
    from models import Article

    profile = user.profile
    if not profile or not profile.main_topic:
        digest.status = 'failed'
        digest.error_message = 'Research profile not configured. Please set up your research topic first.'
        db.session.commit()
        return

    if not user.openai_api_key:
        digest.status = 'failed'
        digest.error_message = 'OpenAI API key not configured. Please add your API key in Settings.'
        db.session.commit()
        return

    client = OpenAI(api_key=user.openai_api_key)
    digest.status = 'processing'
    db.session.commit()

    try:
        query = build_search_query(profile)
        platforms = profile.get_platforms()
        per_platform = max(2, profile.articles_per_day // len(platforms))
        all_articles = []

        if 'arxiv' in platforms:
            all_articles.extend(fetch_arxiv_articles(query, per_platform + 2, profile.exclude_terms))
        if 'semantic_scholar' in platforms:
            all_articles.extend(fetch_semantic_scholar_articles(query, per_platform + 2, profile.exclude_terms))
        if 'pubmed' in platforms:
            all_articles.extend(fetch_pubmed_articles(query, per_platform + 2, profile.exclude_terms))
        if 'crossref' in platforms:
            all_articles.extend(fetch_crossref_articles(query, per_platform + 2, profile.exclude_terms))

        if profile.include_blogs:
            blog_posts = fetch_blog_posts(profile.get_selected_blogs(), query)
            all_articles.extend(blog_posts[:3])

        # Deduplicate by title similarity
        seen_titles = set()
        unique_articles = []
        for a in all_articles:
            title_key = a['title'].lower()[:80]
            if title_key not in seen_titles and len(title_key) > 5:
                seen_titles.add(title_key)
                unique_articles.append(a)

        # Check if these are truly new (not already analyzed)
        existing_urls = {a.url for a in Article.query.filter_by(user_id=user.id).all()}
        new_articles = [a for a in unique_articles if a.get('url') and a['url'] not in existing_urls]

        regenerated = False
        if not new_articles:
            # Regenerate insights from existing articles
            regenerated = True
            existing = Article.query.filter_by(user_id=user.id).order_by(
                Article.relevance_score.desc()
            ).limit(profile.articles_per_day).all()

            if existing:
                for article in existing:
                    article.digest_id = digest.id
                    insights = analyze_article_with_ai(client, {
                        'title': article.title,
                        'authors': article.authors,
                        'abstract': article.abstract,
                        'source_platform': article.source_platform
                    }, profile)
                    if insights:
                        article.summary_highlights = insights.get('highlights', '')
                        article.summary_methodology = insights.get('methodology', '')
                        article.summary_datasets = insights.get('datasets', '')
                        article.summary_models = insights.get('models', '')
                        article.summary_results = insights.get('results', '')
                        article.summary_soul = insights.get('soul', '')
                        article.detail_approach = _str(insights.get('approach_steps', ''))
                        article.detail_methodology = insights.get('detailed_methodology', '')
                        article.detail_results = insights.get('detailed_results', '')
                        article.detail_figures = insights.get('figures_to_review', '')
                        article.detail_writeup_summary = insights.get('writeup_summary', '')
                        article.relevance_score = float(insights.get('relevance_score', 0.5))
                    time.sleep(0.5)

                digest.total_articles = len(existing)
                digest.new_articles_count = 0
                digest.regenerated = True
                digest.status = 'ready'
                db.session.commit()
                return

        # Process new articles
        target_count = min(len(new_articles), profile.articles_per_day)
        processed = 0

        for article_data in new_articles[:target_count]:
            insights = analyze_article_with_ai(client, article_data, profile)
            if not insights:
                continue

            article = Article(
                user_id=user.id,
                digest_id=digest.id,
                title=article_data['title'],
                authors=article_data['authors'],
                abstract=article_data['abstract'],
                url=article_data['url'],
                source_platform=article_data['source_platform'],
                published_date=article_data['published_date'],
                is_blog_post=article_data.get('is_blog_post', False),
                summary_highlights=_str(insights.get('highlights', '')),
                summary_methodology=_str(insights.get('methodology', '')),
                summary_datasets=_str(insights.get('datasets', '')),
                summary_models=_str(insights.get('models', '')),
                summary_results=_str(insights.get('results', '')),
                summary_soul=_str(insights.get('soul', '')),
                detail_approach=_str(insights.get('approach_steps', '')),
                detail_methodology=_str(insights.get('detailed_methodology', '')),
                detail_results=_str(insights.get('detailed_results', '')),
                detail_figures=_str(insights.get('figures_to_review', '')),
                detail_writeup_summary=_str(insights.get('writeup_summary', '')),
                relevance_score=float(insights.get('relevance_score', 0.5))
            )
            db.session.add(article)
            processed += 1
            time.sleep(0.5)

        db.session.flush()
        digest.total_articles = processed
        digest.new_articles_count = processed
        digest.regenerated = False
        digest.status = 'ready'
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        digest.status = 'failed'
        digest.error_message = str(e)[:500]
        try:
            db.session.commit()
        except:
            db.session.rollback()
        print(f"Digest error: {e}")